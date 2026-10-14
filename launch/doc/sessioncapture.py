"""Capture of the session's pages, composed into one image with a caption, and assembly of the
images into a time-lapse video: shared by the recording modes of record_session.py."""

import io
import itertools
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# an image is an event's (a step to read: its caption stays about TIMING["caption"]), a progress
# image (the rounds, the waits: they scroll by) or the final one's
EVENT, PROGRESS, FINAL = "event", "progress", "final"

# blend: share of each image's time spent fading into the next one (0: a cut)
TIMING = {"caption": 3.5, "last_caption": 5.0, "min_frame": 0.25, "round_frame": 0.25,
          "progress_max": 8.0, "end_hold": 2.5, "webp_width": 1080, "blend": 0.4}

# width: the inset's largest share of the image's width (an inset is never enlarged); viewport: the
# window of an agent's tab once its run is launched, narrow so that its run monitor stays readable
INSET = {"width": 0.42, "corner": "bottom-right", "viewport": {"width": 760, "height": 470}}

CAPTION_BACKGROUND, CAPTION_TEXT, INSET_BORDER = (20, 24, 40, 225), (255, 255, 255, 255), (78, 205, 196, 255)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def page_text(page, element_id):
    return page.evaluate(f"() => (document.getElementById('{element_id}') || {{}}).textContent || ''").strip()


def font(size, bold=True):
    # Pillow looks the name up in the system's font directories; any machine without it gets the default
    for name in (("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf") if bold else ("DejaVuSans.ttf", "LiberationSans-Regular.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def view_label(name, page):
    """what an inset shows, as its tab says it: the agent and the page it is on"""
    if name == "manager":
        return "session manager"
    if name.startswith("manager@"):
        return {"geo": "session manager · map", "nodes": "session manager · agents"}.get(name.split("@", 1)[1], "session manager")
    name = name.split("@", 1)[0]
    path = page.url.split("?")[0]
    what = ("run monitor" if path.endswith("/run") else "registration form" if "registration" in path
            else "session form" if path.endswith("/session/config") else "configuration form")
    return f"{name.split(':', 1)[-1]} · {what}"


class Recorder:
    """captures the main view and the inset, if any, and composes them with the caption; Playwright's
    sync API is not thread-safe, so the images are taken between the recording's other actions"""

    def __init__(self, pages: dict, frames: Path, period: float, viewport: dict, scale: float = 1, inset=None):
        self.pages, self.frames, self.period, self.scale, self.n = pages, frames, period, scale, 0
        self.size = (round(viewport["width"] * scale), round(viewport["height"] * scale))
        self.inset_style = {**INSET, **(inset or {})}
        self.main, self.inset = "manager", None
        self.caption_font, self.label_font = font(round(22 * scale)), font(round(14 * scale))
        frames.mkdir(parents=True)
        self.index = open(frames / "captions.tsv", "w")

    def view(self, main, inset=None):
        self.main, self.inset = main, inset

    def capture(self, name):
        """a view is a tab, or a part of it: "<tab>@<element id>", the panel holding the element"""
        tab, _, element = name.partition("@")
        target = self.pages[tab]
        if element:
            located = target.locator(f"#{element}")
            panel = located.locator("xpath=ancestor::section[1]")
            target = panel if panel.count() else located
        return Image.open(io.BytesIO(target.screenshot())).convert("RGBA")

    def compose(self, caption):
        image = self.capture(self.main)
        width, height = self.size
        if image.size != self.size:
            # every image of a video has one size: a main view of another one is fitted to it
            image = image.resize(self.size, Image.LANCZOS)
        s = self.scale
        draw = ImageDraw.Draw(image, "RGBA")
        caption_box = None
        if caption:
            left, top, right, bottom = draw.textbbox((0, 0), caption, font=self.caption_font)
            pad_x, pad_y = 22 * s, 10 * s
            box_w, box_h = right - left + 2 * pad_x, bottom - top + 2 * pad_y
            x0, y0 = (width - box_w) / 2, height - 18 * s - box_h
            caption_box = (x0, y0, x0 + box_w, y0 + box_h)
        if self.inset:
            inset = self.capture(self.inset)
            w = min(int(width * self.inset_style["width"]), inset.width)
            inset = inset.resize((w, int(inset.height * w / inset.width)), Image.LANCZOS)
            margin = 24 * s
            # above the caption, which stays readable
            bottom_room = (height - caption_box[1] + 8 * s) if caption_box else margin
            corner = self.inset_style["corner"]
            x = margin if "left" in corner else width - w - margin
            y = margin + 26 * s if "top" in corner else height - inset.height - bottom_room
            x, y = int(x), int(y)
            image.alpha_composite(inset, (x, y))
            border = max(2, round(2 * s))
            draw.rectangle((x - border, y - border, x + w + border - 1, y + inset.height + border - 1), outline=INSET_BORDER, width=border)
            label = view_label(self.inset, self.pages[self.inset.split("@", 1)[0]])
            l, t, r, b = draw.textbbox((0, 0), label, font=self.label_font)
            draw.rounded_rectangle((x - border, y - (b - t) - 12 * s, x - border + (r - l) + 16 * s, y - border),
                                   radius=6 * s, fill=INSET_BORDER)
            draw.text((x - border + 8 * s, y - (b - t) - 8 * s - t), label, font=self.label_font, fill=(10, 14, 22, 255))
        if caption_box:
            draw.rounded_rectangle(caption_box, radius=10 * s, fill=CAPTION_BACKGROUND)
            l, t, _, _ = draw.textbbox((0, 0), caption, font=self.caption_font)
            draw.text((caption_box[0] + 22 * s - l, caption_box[1] + 10 * s - t), caption, font=self.caption_font, fill=CAPTION_TEXT)
        return image.convert("RGB")

    def shoot(self, caption, kind=PROGRESS, count=1):
        for _ in range(count):
            name = f"f{self.n:05d}.png"
            self.compose(caption).save(self.frames / name)
            self.index.write(f"{name}\t{kind}\t{caption}\n"); self.index.flush()
            self.n += 1
            self.pages[self.main.split("@", 1)[0]].wait_for_timeout(int(self.period * 1000))

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

    def rate(fps):
        if not timing["blend"]:
            return f"fps={fps}"
        # framerate mixes an image with the next one when its position between them is past
        # interp_start (0..255): only the end of each image fades; a change of view stays a cut (scene)
        start = round(255 * (1 - min(max(timing["blend"], 0), 1)))
        return f"framerate=fps={fps}:interp_start={start}:interp_end=255"

    output.parent.mkdir(parents=True, exist_ok=True)
    written = []
    if "mp4" in formats:
        # H.264 in yuv420p needs even sizes, which a fractional scale may not give
        subprocess.run(ff + ["-vf", f"{rate(25)},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264",
                             "-crf", "24", "-preset", "slow", "-movflags", "+faststart", f"{output}.mp4"], check=True)
        written.append(f"{output}.mp4")
    if "webp" in formats:
        subprocess.run(ff + ["-vf", f"{rate(10)},scale={timing['webp_width']}:-1:flags=lanczos", "-c:v", "libwebp_anim",
                             "-lossless", "0", "-q:v", "70", "-loop", "0", f"{output}.webp"], check=True)
        written.append(f"{output}.webp")
    if "png" in formats:
        shutil.copytree(frames, f"{output}-frames", dirs_exist_ok=True)
        written.append(f"{output}-frames")
    for path in written:
        log(f"{path} written")
