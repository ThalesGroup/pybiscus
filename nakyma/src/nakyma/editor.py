"""Interactive editing: a local page showing the rushes on a timeline, with the composed image of the
cut at any moment and the video played from its plan; a scene's settings are changed there, for that
scene (an override) or for every scene of its kind (the rule); screenshots are taken from the
moment shown. All is saved into the cut's file with its comments, and exported from the page as edit
does it."""

import copy
import io
import json
import shutil
import threading
import time
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from .editing import MOSAIC, RULE_KEYS, SLOTS, Composer, Rushes, TIMING, check_shots, edit, plan, scenes, shot_anchor, shot_image
from .shooting import log

PAGE = Path(__file__).with_name("editor.html")
CACHE_SIZE = 400
JPEG_QUALITY = 82
SCENE_KEYS = ("offset", "duration", "corner", "width", "side", "slots", "skip")
SETTING_KEYS = ("output", "formats", "shots_dir")
FORMATS = ("mp4", "webp", "png")
MEDIA_TYPES = {".mp4": "video/mp4", ".webp": "image/webp", ".png": "image/png"}
# the header a write must carry: a page of another site cannot send it without the browser asking first
HEADER = "X-Nakyma-Editor"


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


def flow(value):
    # a list written on one line, as the cuts write [mp4, webp] or ["page:*"]
    if isinstance(value, list):
        value = CommentedSeq(value)
        value.fa.set_flow_style()
    return value


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
        self.disk_mtime, self.scenes, self.frames, self.shots, self.error, self.dirty = None, [], [], [], None, False
        self.export = {"state": "idle"}
        self.reload()
        if self.error:
            raise SystemExit(self.error)

    def reload(self, force=False):
        mtime = self.cut_file.stat().st_mtime
        if mtime == self.disk_mtime and not force:
            return
        document = self.yaml.load(self.cut_file.read_text()) or CommentedMap()
        if not isinstance(document, dict):
            raise SystemExit(f"{self.cut_file}: a cut is a mapping (scenes, shots…)")
        self.document, self.disk_mtime, self.dirty = document, mtime, False
        self.error = None
        try:
            self.compute(plain(document))
        except SystemExit as error:
            # a cut being written may be wrong for a while: the page says why and keeps the last plan
            self.error = str(error)

    def compute(self, cut):
        # a cut of screenshots only has no scene: the page shows the rushes and the shots
        computed = (scenes(self.rushes, cut), plan(self.rushes, cut)) if cut.get("scenes") else ([], [])
        shots = check_shots(self.rushes, cut)
        self.cut, (self.scenes, self.frames), self.shots = cut, computed, shots
        self.composer = Composer(self.rushes, cut.get("inset"), cut.get("mosaic"))
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
            # several keys in one change: tiles replacing an inset, which cannot be set together
            values = op.get("values") or {key: value}
            if op.get("scope") == "shot":
                self.change_shot(document, op)
            elif op.get("scope") == "setting":
                self.change_setting(document, key, value)
            elif kind not in (document.get("scenes") or {}):
                raise Refused(f"no rule for the kind {kind!r}")
            elif op.get("scope") == "rule":
                rule = document["scenes"][kind]
                for key, value in values.items():
                    if key not in RULE_KEYS:
                        raise Refused(f"a rule sets {', '.join(RULE_KEYS)}, not {key!r}")
                    if key == "main" and not value:
                        raise Refused("a scene needs a main view")
                    if value in (None, "", []):
                        rule.pop(key, None)
                    else:
                        rule[key] = flow(value)
            elif op.get("scope") == "scene":
                for key, value in values.items():
                    if key not in RULE_KEYS + SCENE_KEYS:
                        raise Refused(f"an override sets {', '.join(RULE_KEYS + SCENE_KEYS)}, not {key!r}")
                    self.set_override(document, kind, op.get("index"), key, flow(value), op.get("remove", False))
            else:
                raise Refused("scope is rule, scene, shot or setting")
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

    @staticmethod
    def change_setting(document, key, value):
        if key not in SETTING_KEYS:
            raise Refused(f"a setting is {', '.join(SETTING_KEYS)}, not {key!r}")
        if key == "formats":
            if not isinstance(value, list) or not value or set(value) - set(FORMATS):
                raise Refused(f"formats: one or more of {', '.join(FORMATS)}")
            value = CommentedSeq(value)
            value.fa.set_flow_style()
        if value in (None, ""):
            document.pop(key, None)
        else:
            document[key] = value

    def change_shot(self, document, op):
        shots = document.get("shots")
        if shots is None:
            shots = document["shots"] = CommentedSeq()
        if "add" in op:
            add = op["add"]
            if not add.get("file"):
                raise Refused("a shot needs a file name")
            if add.get("take"):
                shot = CommentedMap([("file", add["file"]), ("take", add["take"])])
            else:
                try:
                    anchor = shot_anchor(self.rushes, add["view"], float(add["t"]))
                except SystemExit as error:
                    raise Refused(str(error))
                shot = CommentedMap([("file", add["file"]), ("view", add["view"]), *anchor.items()])
                if add.get("panel"):
                    shot["panel"] = add["panel"]
            # written on one line, as the shots of the docs
            shot.fa.set_flow_style()
            shots.append(shot)
            return
        index = op.get("index")
        if not isinstance(index, int) or not 0 <= index < len(shots):
            raise Refused(f"no shot {index}")
        if op.get("remove"):
            del shots[index]
            if not shots:
                del document["shots"]
        elif op.get("file"):
            shots[index]["file"] = op["file"]
        else:
            raise Refused("a shot is added, removed or renamed")

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

    # ............................................................ export

    def start_export(self):
        with self.lock:
            if self.dirty:
                raise Refused("save first: the export writes what the cut's file says, as edit does")
            if self.export["state"] == "running":
                raise Refused("an export is running")
            if self.error:
                raise Refused(f"the cut has an error: {self.error}")
            cut = copy.deepcopy(self.cut)
            self.export = {"state": "running", "stage": "starting", "done": 0, "total": 0, "written": [],
                           "error": None, "started": time.time(), "elapsed": 0}
        threading.Thread(target=self.run_export, args=(cut,), daemon=True).start()

    def run_export(self, cut):
        export = self.export

        def progress(stage, done=0, total=0):
            export.update(stage=stage, done=done, total=total, elapsed=time.time() - export["started"])

        try:
            written = edit(self.rushes.dir, cut, progress=progress)
            export.update(state="done", written=written)
        # the thread's end: whatever stops the export is shown in the page rather than lost
        except BaseException as error:
            export.update(state="failed", error=str(error) or type(error).__name__)
        export["elapsed"] = time.time() - export["started"]

    def export_json(self):
        export = dict(self.export)
        if export.get("state") == "running":
            export["elapsed"] = time.time() - export["started"]
        export["written"] = [{"path": p, "media": MEDIA_TYPES.get(Path(p).suffix)} for p in export.get("written", [])]
        return export

    def output_file(self, index):
        written = self.export.get("written", []) if self.export.get("state") == "done" else []
        if not 0 <= index < len(written) or Path(written[index]).suffix not in MEDIA_TYPES:
            return None
        return Path(written[index])

    def rushes_json(self):
        r = self.rushes
        views = {name: {"times": [c["t"] for c in captures],
                        # an unchanged page is kept once: the timeline marks the changes
                        "changes": [i for i, c in enumerate(captures) if i == 0 or c["file"] != captures[i - 1]["file"]],
                        "panels": sorted({p for c in captures for p in c["panels"]}),
                        "label": captures[-1]["label"]}
                 for name, captures in r.by_view.items()}
        # a take can come after the last capture: the timeline goes as far
        span = max([r.end] + [take.get("t", 0) for take in r.takes.values()])
        return {"dir": r.dir.name, "size": r.size, "scale": r.scale, "end": r.end, "span": span, "views": views,
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
        written = self.cut.get("shots") or []
        shots = [{**{k: v for k, v in shot.items() if k != "capture"}, "written": written[i]} for i, shot in enumerate(self.shots)]
        return {"cut": self.cut_file.name, "error": self.error, "frames": self.frames, "scenes": listed,
                "skipped": skipped, "video_duration": video_t + timing["end_hold"] if self.frames else 0,
                "rules": self.cut.get("scenes") or {}, "shots": shots, "shots_dir": self.cut.get("shots_dir"),
                "output": self.cut.get("output"), "formats": self.cut.get("formats", ["mp4", "webp"]),
                "default_output": str(self.rushes.dir / "video"),
                "dirty": self.dirty, "disk_changed": self.dirty and self.disk_changed(),
                "inset": {"width": 0.42, "corner": "bottom-right", **(self.cut.get("inset") or {})},
                "mosaic": self.mosaic_defaults()}

    def mosaic_defaults(self):
        mosaic = {**MOSAIC, **(self.cut.get("mosaic") or {})}
        return {"side": mosaic["side"], "slots": mosaic["slots"] or SLOTS.get(mosaic["side"], 4)}

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
        return self.image(("frame", index), lambda: self.composer.frame(f), width)

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
        return self.image(("at", round(t, 3)), lambda: self.composer.frame(f, t), width)

    def shot(self, index, width):
        shot = self.shots[index]
        return self.image(("shot", index), lambda: shot_image(self.rushes, shot), width)

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

    def send_file(self, path):
        # a range: the video element seeks by asking for a part of the file
        size, start, end = path.stat().st_size, 0, None
        ranged = self.headers.get("Range", "").startswith("bytes=")
        if ranged:
            first, _, last = self.headers["Range"][6:].partition("-")
            start, end = int(first or 0), int(last) if last else size - 1
        end = size - 1 if end is None else min(end, size - 1)
        self.send_response(206 if ranged else 200)
        self.send_header("Content-Type", MEDIA_TYPES[path.suffix])
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as source:
            source.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = source.read(min(left, 1 << 20))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

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
            if url.path == "/api/shot":
                index = int(query["i"])
                if not 0 <= index < len(session.shots):
                    return self.json({"error": f"no shot {index}"}, 404)
                return self.send(200, session.shot(index, width), "image/jpeg")
            if url.path == "/api/export":
                return self.json(session.export_json())
            if url.path == "/api/output":
                path = session.output_file(int(query["i"]))
                if not path or not path.is_file():
                    return self.json({"error": "no such file written by the export"}, 404)
                return self.send_file(path)
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
            elif url.path == "/api/export":
                session.start_export()
                return self.json(session.export_json())
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
