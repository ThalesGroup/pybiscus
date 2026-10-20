"""Interactive editing: a local page showing the rushes on a timeline, with the composed image of the
cut at any moment and the video played from its plan. Read-only for now: the cut is edited in its
file, and the page reloads it."""

import io
import json
import threading
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from .editing import Composer, Rushes, TIMING, plan, scenes
from .shooting import log

PAGE = Path(__file__).with_name("editor.html")
CACHE_SIZE = 400
JPEG_QUALITY = 82


class Session:
    """the rushes and the cut being edited; the plan is computed again when the cut's file changes"""

    def __init__(self, rushes_dir: Path, cut_file: Path):
        self.rushes = Rushes(Path(rushes_dir).resolve())
        self.cut_file = Path(cut_file)
        self.lock = threading.Lock()
        self.cache = {}
        self.cut_mtime, self.scenes, self.frames, self.error = None, [], [], None
        self.reload()
        if self.error:
            raise SystemExit(self.error)

    def reload(self):
        mtime = self.cut_file.stat().st_mtime
        if mtime == self.cut_mtime:
            return
        cut = yaml.safe_load(self.cut_file.read_text()) or {}
        if not cut.get("scenes"):
            raise SystemExit(f"{self.cut_file}: no scenes, nothing to edit (a cut of screenshots only is edited as it is)")
        self.cut, self.cut_mtime = cut, mtime
        self.composer = Composer(self.rushes, cut.get("inset"))
        self.error = None
        try:
            self.scenes, self.frames = scenes(self.rushes, cut), plan(self.rushes, cut)
        except SystemExit as error:
            # a cut being written may be wrong for a while: the page says why and keeps the last plan
            self.error = str(error)
        self.cache.clear()

    def state(self):
        with self.lock:
            try:
                self.reload()
            except (OSError, yaml.YAMLError, SystemExit) as error:
                self.error = f"{self.cut_file}: {error}"
            return self.error

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
                "skipped": skipped, "video_duration": video_t + timing["end_hold"], "rules": self.cut["scenes"]}

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
