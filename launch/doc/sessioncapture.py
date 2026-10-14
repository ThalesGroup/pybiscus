"""Capture of the session manager's page with a caption, and assembly of the captures into a
time-lapse video: shared by the recording modes of record_session.py."""

import itertools
import shutil
import subprocess
import time
from pathlib import Path

# a frame is an event's (a step to read: its caption stays about TIMING["caption"]), a progress
# frame (the rounds, the waits: they scroll by) or the final one's
EVENT, PROGRESS, FINAL = "event", "progress", "final"

TIMING = {"caption": 2.2, "last_caption": 4.0, "min_frame": 0.25, "round_frame": 0.12,
          "progress_max": 8.0, "end_hold": 2.5, "webp_width": 1080}

CAPTION_JS = """(t) => { let d = document.getElementById('__caption');
  if (!d) { d = document.createElement('div'); d.id = '__caption';
    d.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;padding:10px 22px;' +
      'border-radius:10px;background:rgba(20,24,40,.88);color:#fff;font:600 22px system-ui,sans-serif;' +
      'box-shadow:0 4px 18px rgba(0,0,0,.35);white-space:nowrap';
    document.body.appendChild(d); }
  d.textContent = t; d.style.display = t ? 'block' : 'none'; }"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def page_text(page, element_id):
    return page.evaluate(f"() => (document.getElementById('{element_id}') || {{}}).textContent || ''").strip()


class Recorder:
    """captures the manager's page with the current caption; Playwright's sync API is not thread-safe,
    so the frames are taken between the recording's other actions"""

    def __init__(self, page, frames: Path, period: float):
        self.page, self.frames, self.period, self.n = page, frames, period, 0
        frames.mkdir(parents=True)
        self.index = open(frames / "captions.tsv", "w")

    def shoot(self, caption, kind=PROGRESS, count=1):
        for _ in range(count):
            self.page.evaluate(CAPTION_JS, caption)
            name = f"f{self.n:05d}.png"
            self.page.screenshot(path=self.frames / name)
            self.index.write(f"{name}\t{kind}\t{caption}\n"); self.index.flush()
            self.n += 1
            self.page.wait_for_timeout(int(self.period * 1000))

    def say(self, caption, hold, kind=EVENT):
        log(caption)
        self.shoot(caption, kind, hold)


def assemble(frames: Path, output: Path, formats, timing=None):
    timing = {**TIMING, **(timing or {})}
    rows = [line.rstrip("\n").split("\t") for line in open(frames / "captions.tsv")]
    if not rows:
        raise SystemExit("nothing was captured")
    lines = []
    for (kind, caption), group in itertools.groupby(rows, key=lambda r: (r[1], r[2])):
        names = [r[0] for r in group]
        if kind == PROGRESS:
            # a long wait would last as long as its frames: it is squeezed into progress_max
            per = min(timing["round_frame"], timing["progress_max"] / len(names))
        else:
            per = max(timing["min_frame"], timing["last_caption" if kind == FINAL else "caption"] / len(names))
        for name in names:
            lines += [f"file '{frames / name}'", f"duration {per:.3f}"]
    final = frames / rows[-1][0]
    lines += [f"file '{final}'", f"duration {timing['end_hold']}", f"file '{final}'"]
    concat = frames / "concat.txt"
    concat.write_text("\n".join(lines) + "\n")
    ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat)]
    output.parent.mkdir(parents=True, exist_ok=True)
    written = []
    if "mp4" in formats:
        # H.264 in yuv420p needs even sizes, which a fractional scale may not give
        subprocess.run(ff + ["-vf", "fps=25,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264", "-crf", "24", "-preset", "slow",
                             "-movflags", "+faststart", f"{output}.mp4"], check=True)
        written.append(f"{output}.mp4")
    if "webp" in formats:
        subprocess.run(ff + ["-vf", f"fps=10,scale={timing['webp_width']}:-1:flags=lanczos", "-c:v", "libwebp_anim",
                             "-lossless", "0", "-q:v", "70", "-loop", "0", f"{output}.webp"], check=True)
        written.append(f"{output}.webp")
    if "png" in formats:
        shutil.copytree(frames, f"{output}-frames", dirs_exist_ok=True)
        written.append(f"{output}-frames")
    for path in written:
        log(f"{path} written")
