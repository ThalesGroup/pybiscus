"""Interactive editing: a local page showing the rushes on a timeline, with the composed image of the
cut at any moment and the video played from its plan; a scene's settings are changed there, for that
scene (an override) or for every scene of its kind (the rule), and saved into the cut's file with
its comments."""

import copy
import io
import json
import shutil
import threading
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from .editing import RULE_KEYS, Composer, Rushes, TIMING, plan, scenes
from .shooting import log

PAGE = Path(__file__).with_name("editor.html")
CACHE_SIZE = 400
JPEG_QUALITY = 82
SCENE_KEYS = ("offset", "duration", "corner", "width", "skip")
# the header a write must carry: a page of another site cannot send it without the browser asking first
HEADER = "X-Rushes-Editor"


def round_trip():
    """a YAML reader and writer keeping the comments, the quotes and the layout of the bundled cuts"""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    # "inset: null" as the docs write it; ruamel writes an empty value otherwise
    yaml.representer.add_representer(type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null"))
    return yaml


def plain(document):
    # the editing reads plain dicts and lists; the document keeps its comments for the writing
    return json.loads(json.dumps(document))


class Refused(Exception):
    pass


class Session:
    """the rushes and the cut being edited. The cut's file is followed while nothing is changed in the
    page; changes are kept here until saved"""

    def __init__(self, rushes_dir: Path, cut_file: Path):
        self.rushes = Rushes(Path(rushes_dir).resolve())
        self.cut_file = Path(cut_file)
        self.yaml = round_trip()
        self.lock = threading.Lock()
        self.cache = {}
        self.disk_mtime, self.scenes, self.frames, self.error, self.dirty = None, [], [], None, False
        self.reload()
        if self.error:
            raise SystemExit(self.error)

    def reload(self, force=False):
        mtime = self.cut_file.stat().st_mtime
        if mtime == self.disk_mtime and not force:
            return
        document = self.yaml.load(self.cut_file.read_text()) or CommentedMap()
        if not document.get("scenes"):
            raise SystemExit(f"{self.cut_file}: no scenes, nothing to edit (a cut of screenshots only is edited as it is)")
        self.document, self.disk_mtime, self.dirty = document, mtime, False
        self.error = None
        try:
            self.compute(plain(document))
        except SystemExit as error:
            # a cut being written may be wrong for a while: the page says why and keeps the last plan
            self.error = str(error)

    def compute(self, cut):
        computed = scenes(self.rushes, cut), plan(self.rushes, cut)
        self.cut, (self.scenes, self.frames) = cut, computed
        self.composer = Composer(self.rushes, cut.get("inset"))
        self.cache.clear()

    def state(self):
        with self.lock:
            try:
                if not self.dirty:
                    self.reload()
            except (OSError, YAMLError, SystemExit) as error:
                self.error = f"{self.cut_file}: {error}"
            return self.error

    def disk_changed(self):
        try:
            return self.cut_file.stat().st_mtime != self.disk_mtime
        except OSError:
            return True

    # ............................................................ changes

    def change(self, op):
        """applies a change to a copy of the cut, keeps it only if the plan can be computed with it"""
        with self.lock:
            document = copy.deepcopy(self.document)
            kind, key, value = op.get("kind"), op.get("key"), op.get("value")
            if kind not in document["scenes"]:
                raise Refused(f"no rule for the kind {kind!r}")
            if op.get("scope") == "rule":
                if key not in RULE_KEYS:
                    raise Refused(f"a rule sets {', '.join(RULE_KEYS)}, not {key!r}")
                rule = document["scenes"][kind]
                if key == "main" and not value:
                    raise Refused("a scene needs a main view")
                if value in (None, ""):
                    rule.pop(key, None)
                else:
                    rule[key] = value
            elif op.get("scope") == "scene":
                if key not in RULE_KEYS + SCENE_KEYS:
                    raise Refused(f"an override sets {', '.join(RULE_KEYS + SCENE_KEYS)}, not {key!r}")
                self.set_override(document, kind, op.get("index"), key, value, op.get("remove", False))
            else:
                raise Refused("scope is rule or scene")
            try:
                self.compute(plain(document))
            except SystemExit as error:
                raise Refused(str(error))
            self.document, self.dirty, self.error = document, True, None

    @staticmethod
    def set_override(document, kind, index, key, value, remove):
        overrides = document.get("overrides")
        if overrides is None:
            overrides = document["overrides"] = CommentedSeq()
        found = next((o for o in overrides if o.get("kind") == kind and o.get("index") == index), None)
        if remove:
            if found is not None:
                found.pop(key, None)
                if set(found) <= {"kind", "index"}:
                    overrides.remove(found)
            if not overrides:
                del document["overrides"]
            return
        if found is None:
            # written on one line, as the overrides of the docs
            found = CommentedMap([("kind", kind), ("index", index)])
            found.fa.set_flow_style()
            overrides.append(found)
        found[key] = value

    def revert(self):
        with self.lock:
            self.reload(force=True)

    def save(self, force=False):
        with self.lock:
            if self.disk_changed() and not force:
                raise Refused("the cut's file changed on disk since it was read: save over it, or revert to it")
            if self.cut_file.exists():
                shutil.copyfile(self.cut_file, self.cut_file.with_name(self.cut_file.name + ".bak"))
            with open(self.cut_file, "w") as out:
                self.yaml.dump(self.document, out)
            self.disk_mtime, self.dirty = self.cut_file.stat().st_mtime, False

    def rushes_json(self):
        r = self.rushes
        views = {name: {"times": [c["t"] for c in captures],
                        # an unchanged page is kept once: the timeline marks the changes
                        "changes": [i for i, c in enumerate(captures) if i == 0 or c["file"] != captures[i - 1]["file"]],
                        "panels": sorted({p for c in captures for p in c["panels"]}),
                        "label": captures[-1]["label"]}
                 for name, captures in r.by_view.items()}
        return {"dir": r.dir.name, "size": r.size, "scale": r.scale, "end": r.end, "views": views,
                "events": r.events, "takes": list(r.takes.values())}

    def plan_json(self):
        timing = {**TIMING, **(self.cut.get("timing") or {})}
        listed, video_t = [], 0.0
        for i, scene in enumerate(self.scenes):
            frames = [f for f in self.frames if f["scene"] == i]
            duration = sum(f["duration"] for f in frames)
            listed.append({"kind": scene["kind"], "index": scene["index"], "start": scene["start"], "end": scene["end"],
                           "fields": {k: v for k, v in scene["event"].items() if k not in ("t", "kind")},
                           "rule": scene["rule"], "override": scene["override"], "inset_style": scene["inset_style"],
                           "frames": len(frames), "video_start": video_t, "video_duration": duration})
            video_t += duration
        skipped = [{"kind": o["kind"], "index": o["index"]} for o in self.cut.get("overrides") or [] if o.get("skip")]
        return {"cut": self.cut_file.name, "error": self.error, "frames": self.frames, "scenes": listed,
                "skipped": skipped, "video_duration": video_t + timing["end_hold"], "rules": self.cut["scenes"],
                "dirty": self.dirty, "disk_changed": self.dirty and self.disk_changed(),
                "inset": {"width": 0.42, "corner": "bottom-right", **(self.cut.get("inset") or {})}}

    def image(self, key, compose, width):
        key = (key, width)
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        image = compose()
        if width and width < image.width:
            image = image.resize((width, round(image.height * width / image.width)))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=JPEG_QUALITY)
        data = buffer.getvalue()
        with self.lock:
            if len(self.cache) >= CACHE_SIZE:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = data
        return data

    def frame(self, index, width):
        f = self.frames[index]
        return self.image(("frame", index), lambda: self.composer.compose(f["t"], f["main"], f["inset"], f["caption"], f["inset_style"]), width)

    def at(self, t, width):
        """the image of the cut at a moment of the rushes: the scene in progress then, composed at t"""
        current = None
        for i, scene in enumerate(self.scenes):
            if scene["start"] <= t:
                current = i
        index = next((n for n, f in enumerate(self.frames) if f["scene"] == (current or 0)), None)
        if index is None:
            return None
        f = self.frames[index]
        return self.image(("at", round(t, 3)), lambda: self.composer.compose(t, f["main"], f["inset"], f["caption"], f["inset_style"]), width)

    def view(self, name, t, width):
        return self.image(("view", name, round(t, 3)), lambda: self.rushes.image(self.rushes.at(name, t)).convert("RGB"), width)


class Handler(BaseHTTPRequestHandler):
    def __init__(self, session, *args, **kwargs):
        self.session = session
        super().__init__(*args, **kwargs)

    def log_message(self, *args):
        pass

    def send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, data, code=200):
        self.send(code, json.dumps(data).encode(), "application/json")

    def do_GET(self):
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        width = int(query.get("w", 0)) or None
        session = self.session
        try:
            if url.path == "/":
                return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/rushes":
                return self.json(session.rushes_json())
            if url.path == "/api/plan":
                session.state()
                return self.json(session.plan_json())
            if url.path == "/api/frame":
                index = int(query["i"])
                if not 0 <= index < len(session.frames):
                    return self.json({"error": f"no image {index} in the plan"}, 404)
                return self.send(200, session.frame(index, width), "image/jpeg")
            if url.path == "/api/at":
                data = session.at(float(query["t"]), width)
                return self.send(200, data, "image/jpeg") if data else self.json({"error": "no scene"}, 404)
            if url.path == "/api/view":
                if query.get("view") not in session.rushes.by_view:
                    return self.json({"error": f"no view {query.get('view')!r}"}, 404)
                return self.send(200, session.view(query["view"], float(query["t"]), width), "image/jpeg")
            return self.json({"error": "not found"}, 404)
        except (KeyError, ValueError) as error:
            return self.json({"error": f"bad request: {error}"}, 400)
        except (BrokenPipeError, ConnectionResetError):
            # the page moved on (playing, scrubbing) before an image arrived
            pass

    def do_POST(self):
        if self.headers.get(HEADER) != "1":
            return self.json({"error": f"a change carries the header {HEADER}: 1"}, 403)
        url, session = urlparse(self.path), self.session
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if url.path == "/api/change":
                session.change(body)
            elif url.path == "/api/save":
                session.save(bool(body.get("force")))
            elif url.path == "/api/revert":
                session.revert()
            else:
                return self.json({"error": "not found"}, 404)
            return self.json(session.plan_json())
        except Refused as error:
            return self.json({"error": str(error)}, 409)
        except (ValueError, OSError, YAMLError, SystemExit) as error:
            return self.json({"error": str(error)}, 400)


def serve(rushes_dir: Path, cut_file: Path, port: int = 0, open_browser: bool = True):
    session = Session(rushes_dir, cut_file)
    # the loopback only: the page reads every capture of the rushes
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, session))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    log(f"editing {session.rushes.dir.name} with {cut_file}: {url} (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
