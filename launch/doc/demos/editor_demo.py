# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "pyyaml", "pillow", "ruamel.yaml>=0.19.1"]
# ///
"""Shoot a demonstration of the rushes editor (edit --ui) at work on rushes, then edit it into a video.

    uv run launch/doc/demos/editor_demo.py <rushes of the MNIST scenario>

The editor is a web application like another: this driver uses the shooting of launch/doc/rushes and
nothing of Pybiscus. Events: open, play, caption, mosaic, skip, shot, save, export, done."""

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

DOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOC))
from rushes import Shooting, edit, log  # noqa: E402

# wide enough for the header to hold on one line
VIEWPORT = {"width": 1600, "height": 900}
PANELS = (("preview", "#preview-box"), ("timeline", "#timeline-wrap"), ("scene", "#scene"), ("shots", "#shots-box"))
# a headless capture shows no mouse: a disc moves to what is clicked, so that the video shows it
CURSOR_JS = """() => { const c = document.createElement('div'); c.id = 'demo-cursor';
  c.style.cssText = 'position:fixed;left:60%;top:40%;width:24px;height:24px;margin:-12px 0 0 -12px;border-radius:50%;' +
    'background:rgba(255,209,102,.45);border:2px solid #ffd166;z-index:99999;pointer-events:none;' +
    'transition:left .45s ease, top .45s ease, transform .12s';
  document.body.appendChild(c); }"""
MOVE_JS = """([x, y]) => { const c = document.getElementById('demo-cursor'); c.style.left = x + 'px'; c.style.top = y + 'px'; }"""
PRESS_JS = """(down) => { document.getElementById('demo-cursor').style.transform = down ? 'scale(.6)' : ''; }"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Demo:
    def __init__(self, page, shooting):
        self.page, self.shooting = page, shooting

    def tick(self, n=1):
        self.shooting.tick(n)

    def point(self, target):
        if isinstance(target, tuple):
            return target
        box = self.page.locator(target).first.bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def click(self, target):
        x, y = self.point(target)
        self.page.evaluate(MOVE_JS, [x, y]); self.tick(2)
        self.page.evaluate(PRESS_JS, True)
        self.page.mouse.click(x, y)
        self.page.evaluate(PRESS_JS, False); self.tick(1)

    def type(self, selector, text):
        # by a few letters between two captures: the video shows the text being written
        self.click(selector)
        self.page.fill(selector, "")
        for i in range(0, len(text), 3):
            self.page.type(selector, text[i:i + 3]); self.tick(1)
        self.page.press(selector, "Tab"); self.settle(); self.tick(3)

    def settle(self):
        # a change goes to the server, which answers with the new plan: the page is drawn again after it
        self.page.wait_for_timeout(400)

    def choose(self, selector, value):
        # the cursor goes to the list, without opening it: a headless capture would show its options over the page
        x, y = self.point(selector)
        self.page.evaluate(MOVE_JS, [x, y]); self.tick(2)
        self.page.select_option(selector, value); self.tick(2)

    def scroll(self, script):
        self.page.evaluate(script); self.tick(3)

    def scene(self, kind, index):
        """the scene's block on the video bar, always on screen, unlike the timeline below"""
        n = self.page.evaluate("([k, i]) => cut.scenes.findIndex(s => s.kind === k && s.index === i)", [kind, index])
        return f"#videobar .blk[data-i='{n}']"

    def track(self, view, t):
        """the point of a view's track at the time t of the rushes"""
        return tuple(self.page.evaluate("""([view, t]) => {
            const svg = document.getElementById('timeline'), r = svg.getBoundingClientRect();
            const row = rows().findIndex(x => x.kind === 'view' && x.name === view);
            const box = document.querySelector(`[data-row='${row}']`).getBoundingClientRect();
            return [r.left + LABEL_W + (r.width - LABEL_W - 10) * (t - view0) / (view1 - view0), box.top + box.height / 2]; }""",
            [view, t]))


def play(page, shooting):
    demo, event = Demo(page, shooting), shooting.event
    # the timeline lies below the page's fold: the page scrolls to it, as one would
    down = "() => window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'smooth'})"
    up = "() => window.scrollTo({top: 0, behavior: 'smooth'})"

    event("open"); demo.tick(6)
    demo.scroll(down); demo.tick(5); demo.scroll(up); demo.tick(2)

    event("play")
    demo.click("#b-play"); demo.tick(14); demo.click("#b-play"); demo.tick(2)

    event("caption")
    demo.click(demo.scene("registered", 1)); demo.tick(2)
    demo.type("#f-caption", "2 · A second agent joins: {name}")
    demo.tick(3)

    event("mosaic")
    demo.click(demo.scene("round", 2)); demo.tick(1)
    demo.click("[data-scope=rule]"); demo.tick(1)
    demo.type("#f-tiles", "agent:*")
    demo.type("#f-highlight", "agent:{turn}")
    demo.click(demo.scene("round", 2)); demo.tick(3)
    demo.click("#b-play"); demo.tick(8); demo.click("#b-play"); demo.tick(2)

    event("skip")
    demo.click(demo.scene("launched", 1)); demo.tick(1)
    demo.click("[data-scope=scene]"); demo.tick(1)
    demo.click("#b-skip"); demo.settle(); demo.tick(4)
    demo.click("#b-restore"); demo.settle(); demo.tick(3)

    event("shot")
    end = page.evaluate("() => cut.scenes.find(s => s.kind === 'finished').start + 1")
    # scrolled down, the timeline, the preview and the screenshots' form are on screen together
    demo.scroll(down)
    demo.click(demo.track("manager", end)); demo.tick(2)
    # the side panel scrolls on its own: its screenshots' form brought near the top of the window
    demo.scroll("""() => { const aside = document.querySelector('aside'), box = document.getElementById('shots-box');
        aside.scrollTo({top: aside.scrollTop + box.getBoundingClientRect().top - 60, behavior: 'smooth'}); }""")
    demo.choose("#s-panel", "accChart")
    demo.click("#b-shot"); demo.settle(); demo.tick(5)
    demo.scroll(up)
    demo.scroll("() => document.querySelector('aside').scrollTo({top: 0, behavior: 'smooth'})")

    event("save")
    demo.click("#b-save"); demo.settle(); demo.tick(4)

    event("export")
    demo.click("#b-export")
    page.wait_for_function("() => ['running', 'done', 'failed'].includes(document.getElementById('export').dataset.state)")
    deadline = time.time() + 300
    while page.evaluate("() => document.getElementById('export').dataset.state") == "running" and time.time() < deadline:
        demo.tick()
    # Chromium without H.264 (that of Playwright) plays the animated webp the export wrote beside the mp4
    page.wait_for_function("() => document.querySelector('#export video, #export .webp')", timeout=30000)
    page.evaluate("() => { const v = document.querySelector('#export video'); if (v) { v.muted = true; v.play(); } }")
    page.wait_for_timeout(1000)

    event("done"); demo.tick(10)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="rushes the editor works on (those of launch/doc/scenarios/mnist-session.yml)")
    parser.add_argument("--rushes", type=Path, help="directory of the demo's rushes (default: experiments/recordings/rushes-editor-demo-<date>)")
    parser.add_argument("--cut", default=str(Path(__file__).with_name("editor-demo.cut.yml")), help='cut of the video ("none": no editing)')
    parser.add_argument("--output", type=Path, help="basename of the video, instead of the cut's")
    parser.add_argument("--keep", action="store_true", help="keep the editor's working directory")
    args = parser.parse_args()

    rushes = (args.rushes or Path(f"experiments/recordings/rushes-editor-demo-{time.strftime('%Y%m%d-%H%M%S')}")).resolve()
    if rushes.exists() and any(rushes.iterdir()):
        parser.error(f"--rushes {rushes}: not empty")
    # a short and neutral directory: the export shows the paths it writes
    work = Path(tempfile.mkdtemp(prefix="pybiscus-demo-", dir="/tmp"))
    (work / args.source.resolve().name).symlink_to(args.source.resolve())
    cut = yaml.safe_load((DOC / "scenarios/mnist-session.cut.yml").read_text())
    (work / "mnist-session.cut.yml").write_text((DOC / "scenarios/mnist-session.cut.yml").read_text()
                                                .replace(f"output: {cut['output']}", "output: videos/mnist-session"))
    port = free_port()
    server = subprocess.Popen(["uv", "run", str(DOC / "record_session.py"), "edit", args.source.resolve().name, "mnist-session.cut.yml",
                               "--ui", "--port", str(port), "--no-browser"], cwd=work, stdout=open(work / "editor.log", "w"),
                              stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/plan", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        with sync_playwright() as p:
            page = p.chromium.launch().new_page(viewport=VIEWPORT)
            page.goto(f"http://127.0.0.1:{port}/"); page.wait_for_timeout(2500)
            page.evaluate(CURSOR_JS)
            shooting = Shooting(rushes, VIEWPORT)
            shooting.add_view("editor", page, PANELS, lambda page: "rushes editor")
            shooting.set_focus("editor")
            play(page, shooting)
    finally:
        os.killpg(server.pid, signal.SIGTERM)
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
    log(f"rushes in {rushes}")
    if args.cut != "none":
        edit(rushes, yaml.safe_load(Path(args.cut).read_text()), args.output)


if __name__ == "__main__":
    main()
