# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "nakyma"]
#
# [tool.uv.sources]
# # the package of this repository, editable: a change to it is seen without reinstalling
# nakyma = { path = "../..", editable = true }
# ///
"""Film the shared task list (app.py): Alice and Bob each have a page; one adds or checks a task,
the other's page follows. Then edit the rushes with todo.cut.yml into a video and a screenshot.

    uv run shoot.py [--rushes DIR] [--cut CUT | --cut none]

Events: open; add (who, other, text); done (who, other, text); end (done, total)."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from nakyma import Shooting, log
from nakyma.cli import edit_file

HERE = Path(__file__).resolve().parent

VIEWPORT = {"width": 1280, "height": 720}
PANELS = ("list", "stats", "activity")
PEOPLE = ("alice", "bob")
STORY = [("add", "alice", "Book the meeting room"), ("add", "bob", "Write the agenda"),
         ("add", "alice", "Send the invitations"), ("done", "bob", "Book the meeting room"),
         ("done", "alice", "Write the agenda")]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_served(url):
    for _ in range(100):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(0.1)
    raise SystemExit(f"{url} does not answer")


def play(shooting, pages):
    shooting.event("open")
    shooting.tick(6)
    for kind, who, text in STORY:
        other = next(p for p in PEOPLE if p != who)
        page = pages[who]
        # the one acting is captured at every tick, the other one too: the story is its page following
        shooting.set_focus(f"page:{who}", f"page:{other}")
        shooting.event(kind, who=who, other=other, text=text)
        shooting.tick(2)
        if kind == "add":
            # by a few letters between two captures: the video shows the text being written
            for i in range(0, len(text), 4):
                page.type("#text", text[i:i + 4]); shooting.tick(1)
            page.press("#text", "Enter")
        else:
            page.locator("li", has_text=text).locator("input").check()
        # the other page polls every 0.5 s: a few ticks show it catching up
        shooting.tick(6)
    done, total = pages["alice"].locator("#count").inner_text().split(" / ")
    shooting.event("end", done=done, total=total)
    shooting.tick(6)
    shooting.take("activity", pages["bob"], panel="activity")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rushes", type=Path, help="directory of the rushes (default: rushes-todo-<date> here)")
    parser.add_argument("--cut", default=str(HERE / "todo.cut.yml"), help='cut edited after the shooting ("none": no editing)')
    args = parser.parse_args()
    rushes = (args.rushes or Path(f"rushes-todo-{time.strftime('%Y%m%d-%H%M%S')}")).resolve()
    if rushes.exists() and any(rushes.iterdir()):
        parser.error(f"--rushes {rushes}: not empty")

    port = free_port()
    # its own process group, stopped as a whole at the end, whatever happens
    app = subprocess.Popen([sys.executable, str(HERE / "app.py"), str(port)], start_new_session=True)
    try:
        url = f"http://127.0.0.1:{port}"
        wait_until_served(url)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            shooting = Shooting(rushes, VIEWPORT)
            pages = {}
            for who in PEOPLE:
                pages[who] = browser.new_page(viewport=VIEWPORT)
                pages[who].goto(f"{url}/?who={who}")
                shooting.add_view(f"page:{who}", pages[who], PANELS, label=lambda page, who=who: f"{who.capitalize()}'s page")
            play(shooting, pages)
            browser.close()
    finally:
        os.killpg(app.pid, signal.SIGTERM)
    log(f"rushes in {rushes}")
    if args.cut != "none":
        edit_file(rushes, args.cut)


if __name__ == "__main__":
    main()
