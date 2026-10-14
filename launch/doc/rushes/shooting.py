"""Shooting: the pages of a web application captured while a driver plays it, kept as rushes.

A rushes directory holds:
- meta.json: the viewport, the pixel scale, the views;
- captures.jsonl: one line per capture, {t, view, file, url, label, panels: {id: [x, y, w, h]}}, t in
  seconds since the start, panels in image pixels;
- events.jsonl: one line per event the driver reports, {t, kind, ...its fields};
- takes.jsonl and takes/: special captures the driver asks for (a whole page, a panel after a click);
- views/<view>/<n>.png: the images, an image identical to the view's previous one being kept once.
"""

import hashlib
import json
import time
from pathlib import Path

PANELS_JS = """(ids) => Object.fromEntries(ids.map(id => {
  const el = document.getElementById(id); if (!el) return [id, null];
  const r = (el.closest('section') || el).getBoundingClientRect();
  return [id, [r.x, r.y, r.width, r.height]]; }))"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Shooting:
    """the views are named by the driver; the focused ones are captured at every tick, the others
    every `slow_every` ticks, so that many open pages do not space the captures out"""

    def __init__(self, rushes: Path, viewport: dict, scale: float = 1, period: float = 0.35, slow_every: int = 4):
        self.rushes, self.scale, self.period, self.slow_every = rushes, scale, period, slow_every
        self.size = (round(viewport["width"] * scale), round(viewport["height"] * scale))
        self.views, self.focus, self.ticks, self.start = {}, set(), 0, time.monotonic()
        self.last_digest, self.count = {}, 0
        (rushes / "views").mkdir(parents=True, exist_ok=True)
        (rushes / "takes").mkdir(exist_ok=True)
        self.captures = open(rushes / "captures.jsonl", "a")
        self.events = open(rushes / "events.jsonl", "a")
        self.takes = open(rushes / "takes.jsonl", "a")
        self.write_meta(viewport)

    def write_meta(self, viewport):
        meta = {"viewport": viewport, "scale": self.scale, "size": list(self.size)}
        (self.rushes / "meta.json").write_text(json.dumps(meta, indent=2))

    def now(self):
        return round(time.monotonic() - self.start, 3)

    def add_view(self, name, page, panels=(), label=None):
        """label: what the view shows, as a function of its page (its URL changes as it goes)"""
        self.views[name] = {"page": page, "panels": list(panels), "label": label or (lambda page: name)}
        (self.rushes / "views" / self.safe(name)).mkdir(exist_ok=True)

    def remove_view(self, name):
        self.views.pop(name, None)
        self.focus.discard(name)

    def set_focus(self, *names):
        self.focus = {n for n in names if n in self.views}

    def event(self, kind, **fields):
        self.events.write(json.dumps({"t": self.now(), "kind": kind, **fields}) + "\n"); self.events.flush()

    @staticmethod
    def safe(name):
        return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)

    def capture(self, name):
        view = self.views[name]
        page = view["page"]
        t = self.now()
        png = page.screenshot()
        digest = hashlib.sha1(png).hexdigest()
        if self.last_digest.get(name, (None,))[0] == digest:
            file = self.last_digest[name][1]
        else:
            file = f"views/{self.safe(name)}/{self.count:06d}.png"
            (self.rushes / file).write_bytes(png)
            self.last_digest[name] = (digest, file)
            self.count += 1
        panels = page.evaluate(PANELS_JS, view["panels"]) if view["panels"] else {}
        panels = {k: [round(v * self.scale) for v in box] for k, box in panels.items() if box}
        self.captures.write(json.dumps({"t": t, "view": name, "file": file, "url": page.url,
                                        "label": view["label"](page), "panels": panels}) + "\n")

    def tick(self, count=1):
        for _ in range(count):
            for name in list(self.views):
                if name in self.focus or self.ticks % self.slow_every == 0:
                    self.capture(name)
            self.captures.flush()
            self.ticks += 1
            time.sleep(self.period)

    def take(self, name, page, full_page=False, panel=None):
        """a special capture: the whole page, or a panel (the section holding an element)"""
        path = self.rushes / "takes" / f"{self.safe(name)}.png"
        if panel:
            located = page.locator(f"#{panel}")
            section = located.locator("xpath=ancestor::section[1]")
            (section if section.count() else located).screenshot(path=path)
        else:
            page.screenshot(path=path, full_page=full_page)
        self.takes.write(json.dumps({"t": self.now(), "name": name, "file": f"takes/{path.name}"}) + "\n"); self.takes.flush()
        log(f"take {name}")
