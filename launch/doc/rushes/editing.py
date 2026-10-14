"""Editing: rushes and a cut (the scenes, the screenshots) into a video and images.

A cut (YAML):
    output: docs/videos/my-video          # .mp4, .webp added (default: <rushes>/video); formats: [mp4, webp, png]
    timing: {...}                         # see TIMING
    inset: {width: 0.42, corner: bottom-right}
    scenes:                               # one rule per kind of event; an event starts a scene, which
      <kind>:                             # lasts until the next event having a rule
        main: <view>                      # a view, or a panel of one: "<view>@<panel id>"
        inset: <view>                     # optional
        caption: "text with {fields} of the event"
        pace: event | progress | final    # event: about timing.caption seconds; progress: scrolls by
    shots:                                # screenshots
      - {file: a.png, take: <take name>}
      - {file: b.png, view: <view>, at: <event kind>, index: 0, panel: <panel id>}
    shots_dir: docs/images
Fields and views are written with {name} placeholders, filled from the event's fields.
"""

import bisect
import io
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .shooting import log

TIMING = {"caption": 3.5, "last_caption": 5.0, "min_frame": 0.25, "round_frame": 0.25,
          "progress_max": 8.0, "end_hold": 2.5, "webp_width": 1080, "blend": 0.4}
INSET = {"width": 0.42, "corner": "bottom-right"}
CAPTION_BACKGROUND, CAPTION_TEXT, INSET_BORDER = (20, 24, 40, 225), (255, 255, 255, 255), (78, 205, 196, 255)


def font(size):
    # Pillow looks the name up in the system's font directories; any machine without it gets the default
    for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def read_lines(path):
    return [json.loads(line) for line in open(path)] if path.is_file() else []


class Rushes:
    def __init__(self, directory: Path):
        self.dir = directory
        self.meta = json.loads((directory / "meta.json").read_text())
        self.size = tuple(self.meta["size"])
        self.scale = self.meta["scale"]
        self.events = sorted(read_lines(directory / "events.jsonl"), key=lambda e: e["t"])
        self.takes = {t["name"]: t for t in read_lines(directory / "takes.jsonl")}
        self.by_view = {}
        for c in sorted(read_lines(directory / "captures.jsonl"), key=lambda c: c["t"]):
            self.by_view.setdefault(c["view"], []).append(c)
        self.end = max((c[-1]["t"] for c in self.by_view.values()), default=0)

    def at(self, view, t):
        """the view's capture shown at t: the last one before, else the first one after"""
        captures = self.by_view.get(view)
        if not captures:
            raise SystemExit(f"no capture of the view {view!r} in {self.dir} (views: {', '.join(self.by_view)})")
        i = bisect.bisect_right([c["t"] for c in captures], t)
        return captures[i - 1] if i else captures[0]

    def image(self, capture, panel=None):
        image = Image.open(self.dir / capture["file"]).convert("RGBA")
        if panel:
            box = capture["panels"].get(panel)
            if not box:
                raise SystemExit(f"no panel {panel!r} in the captures of {capture['view']!r} (panels: {', '.join(capture['panels'])})")
            x, y, w, h = box
            image = image.crop((max(0, x), max(0, y), min(image.width, x + w), min(image.height, y + h)))
        return image


class Composer:
    def __init__(self, rushes: Rushes, inset=None):
        self.rushes, self.inset_style = rushes, {**INSET, **(inset or {})}
        s = rushes.scale
        self.caption_font, self.label_font = font(round(22 * s)), font(round(14 * s))

    def view(self, spec, t):
        name, _, panel = spec.partition("@")
        capture = self.rushes.at(name, t)
        return self.rushes.image(capture, panel or None), capture["label"] + (f" · {panel}" if panel else "")

    def compose(self, t, main, inset=None, caption=""):
        rushes, s = self.rushes, self.rushes.scale
        image, _ = self.view(main, t)
        if image.size != rushes.size:
            # every image of a video has one size: a main view of another one (a panel) is fitted to it
            image = image.resize(rushes.size, Image.LANCZOS)
        width, height = rushes.size
        draw = ImageDraw.Draw(image, "RGBA")
        caption_box = None
        if caption:
            left, top, right, bottom = draw.textbbox((0, 0), caption, font=self.caption_font)
            box_w, box_h = right - left + 44 * s, bottom - top + 20 * s
            x0, y0 = (width - box_w) / 2, height - 18 * s - box_h
            caption_box = (x0, y0, x0 + box_w, y0 + box_h)
        if inset:
            small, label = self.view(inset, t)
            # an inset is never enlarged: its text stays readable
            w = min(int(width * self.inset_style["width"]), small.width)
            small = small.resize((w, max(1, int(small.height * w / small.width))), Image.LANCZOS)
            margin = 24 * s
            bottom_room = (height - caption_box[1] + 8 * s) if caption_box else margin
            corner = self.inset_style["corner"]
            x = int(margin if "left" in corner else width - w - margin)
            y = int(margin + 26 * s if "top" in corner else height - small.height - bottom_room)
            image.alpha_composite(small, (x, y))
            border = max(2, round(2 * s))
            draw.rectangle((x - border, y - border, x + w + border - 1, y + small.height + border - 1), outline=INSET_BORDER, width=border)
            l, t_, r, b = draw.textbbox((0, 0), label, font=self.label_font)
            draw.rounded_rectangle((x - border, y - (b - t_) - 12 * s, x - border + (r - l) + 16 * s, y - border),
                                   radius=6 * s, fill=INSET_BORDER)
            draw.text((x - border + 8 * s, y - (b - t_) - 8 * s - t_), label, font=self.label_font, fill=(10, 14, 22, 255))
        if caption_box:
            draw.rounded_rectangle(caption_box, radius=10 * s, fill=CAPTION_BACKGROUND)
            l, t_, _, _ = draw.textbbox((0, 0), caption, font=self.caption_font)
            draw.text((caption_box[0] + 22 * s - l, caption_box[1] + 10 * s - t_), caption, font=self.caption_font, fill=CAPTION_TEXT)
        return image.convert("RGB")


def fill(text, fields):
    return text.format(**fields) if text else text


def scenes(rushes: Rushes, rules: dict):
    """an event with a rule starts a scene, which lasts until the next one"""
    starts = [e for e in rushes.events if e["kind"] in rules]
    for i, event in enumerate(starts):
        end = starts[i + 1]["t"] if i + 1 < len(starts) else rushes.end + 1e-3
        yield event, end, rules[event["kind"]]


def edit(rushes_dir: Path, cut: dict, output=None, work=None):
    # ffmpeg reads the images' names relative to the list that gives them
    rushes_dir = Path(rushes_dir).resolve()
    rushes = Rushes(rushes_dir)
    composer = Composer(rushes, cut.get("inset"))
    written = []
    if cut.get("scenes"):
        output = Path(output or cut.get("output") or rushes_dir / "video").resolve()
        frames = Path(work or rushes_dir / "edit").resolve()
        shutil.rmtree(frames, ignore_errors=True); frames.mkdir(parents=True)
        timing = {**TIMING, **(cut.get("timing") or {})}
        lines, n = [], 0
        for event, end, rule in scenes(rushes, cut["scenes"]):
            fields = {k: v for k, v in event.items() if k not in ("t", "kind")}
            if "main" not in rule:
                raise SystemExit(f"the cut's scene {event['kind']!r} has no main view")
            main, inset = fill(rule["main"], fields), fill(rule.get("inset"), fields)
            caption, pace = fill(rule.get("caption", ""), fields), rule.get("pace", "event")
            main_view = main.partition("@")[0]
            times = [c["t"] for c in rushes.by_view.get(main_view, []) if event["t"] <= c["t"] < end] or [event["t"]]
            if pace == "progress":
                per = min(timing["round_frame"], timing["progress_max"] / len(times))
            else:
                per = max(timing["min_frame"], timing["last_caption" if pace == "final" else "caption"] / len(times))
            for t in times:
                name = f"f{n:05d}.png"; n += 1
                composer.compose(t, main, inset, caption).save(frames / name)
                lines += [f"file '{frames / name}'", f"duration {per:.3f}"]
        if not lines:
            raise SystemExit("no scene: none of the cut's events is in the rushes")
        final = lines[-2].split("'")[1]
        lines += [f"file '{final}'", f"duration {timing['end_hold']}", f"file '{final}'"]
        written += assemble(frames, lines, output, cut.get("formats", ["mp4", "webp"]), timing)
    if cut.get("shots"):
        shots_dir = Path(cut.get("shots_dir", "shots")).resolve()
        shots_dir.mkdir(parents=True, exist_ok=True)
        for shot in cut["shots"]:
            path = shots_dir / shot["file"]
            if "take" in shot:
                take = rushes.takes.get(shot["take"])
                if not take:
                    raise SystemExit(f"no take {shot['take']!r} in {rushes_dir} (takes: {', '.join(rushes.takes)})")
                shutil.copyfile(rushes_dir / take["file"], path)
            else:
                matching = [e for e in rushes.events if e["kind"] == shot["at"]]
                if not matching:
                    raise SystemExit(f"shot {shot['file']}: no event {shot['at']!r} in {rushes_dir}")
                t = matching[shot.get("index", 0)]["t"]
                # the view as it was just after the event: its first capture from then on
                captures = [c for c in rushes.by_view.get(shot["view"], []) if c["t"] >= t] or [rushes.at(shot["view"], t)]
                rushes.image(captures[0], shot.get("panel")).convert("RGB").save(path)
            written.append(str(path))
    for path in written:
        log(f"{path} written")


def assemble(frames: Path, lines, output: Path, formats, timing):
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
    return written
