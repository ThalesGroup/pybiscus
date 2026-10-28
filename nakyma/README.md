# Näkymä

*Näkymä* (Finnish: a view) films a web application made of several pages, and edits what it
filmed into videos and screenshots. It works in two times, as a film does:

1. **shoot**: a **driver** (a Python script using Playwright) plays the application; Näkymä
   captures each page it is given, by name, as a **view**, and notes the **events** the driver
   reports (someone joins, a task is added, round 3…). The result is a directory of **rushes**.
2. **edit**: a **cut** (YAML) says what to make of the rushes: the scenes of a video (for each kind
   of event, the main view, an inset or tiles, a caption, a pace) and the screenshots to extract.
   Editing takes seconds and can be done again with another cut, without shooting again.

What it is made for: **several pages followed together** (one per person, per machine, per role),
composed in one image, the scenes cut **on the application's events** rather than on the steps of a
script. One shooting gives the video and the screenshots of the docs.

> Näkymä lives in the Pybiscus repository for now (`nakyma/`, a project of its own with its
> `pyproject.toml`), which films its federated learning sessions with it
> ([docs/recording.md](../docs/recording.md)); it imports nothing of Pybiscus and is meant to move
> to a repository of its own.

## Prerequisites

- Python 3.12, with Pillow and `ruamel.yaml` (≥ 0.19.1) to edit; Playwright to shoot.
- **ffmpeg** on the `PATH`, with its H.264 and WebP encoders (Debian, Ubuntu: `sudo apt install ffmpeg`).
- The DejaVu or Liberation fonts for the captions (Debian, Ubuntu: `sudo apt install fonts-dejavu-core`);
  without them, the captions use Pillow's default font, with a warning.
- The Chromium of the Playwright the driver pins (`uv run --with playwright==1.63.0 playwright install chromium`).

Until it is published, Näkymä is installed from this directory:

- the `nakyma` command: `uv tool install --editable <repo>/nakyma`, or
  `uv run --project <repo>/nakyma nakyma …` without installing it;
- a driver (a script with a PEP 723 header) declares it as a local, editable dependency:

  ```python
  # /// script
  # dependencies = ["playwright==1.63.0", "nakyma"]
  #
  # [tool.uv.sources]
  # nakyma = { path = "<path to nakyma/, relative to the script>", editable = true }
  # ///
  ```

## An example: a shared task list

`examples/todo/` holds a small application (`app.py`: a task list shared by everyone who opens it,
each page following the others' changes), its driver (`shoot.py`) and its cut (`todo.cut.yml`).
Alice and Bob each have a page; one adds or checks a task, the other's page follows:

```bash
cd /tmp/todo-demo        # any directory: the rushes and the screenshots are written there
uv run <repo>/nakyma/examples/todo/shoot.py
# rushes-todo-<date>/ with its video.mp4 and video.webp (30 s), shots/ with two screenshots
```

The driver is about 80 lines: start the application on a free port in its own process group, open
a page per person, declare each as a view with its panels, then for each step of the story report
an event and tick while acting. It is the model to follow for another application.

## Shooting

```python
from nakyma import Shooting

shooting = Shooting(rushes_dir, viewport={"width": 1280, "height": 720}, scale=1, period=0.35)
shooting.add_view("page:alice", page, panels=("list", "stats"), label=lambda page: "Alice's page")
shooting.set_focus("page:alice")                 # captured at every tick, the others one in four
shooting.event("add", who="alice", text="…")     # a moment of the story, its fields for the captions
shooting.tick(3)                                 # captures, period seconds apart
shooting.take("activity", page, panel="activity")  # a special capture: a whole page, a panel
```

- **Views** are named by the driver; a name with a family, `page:alice`, lets a cut take them all
  (`page:*`). The **label**, computed at each capture from the page (its URL changes as it goes), is
  the text shown on an inset or a tile.
- **Panels** are parts of a page a cut can show alone (`view@panel`), noted at each capture:
  - an element's `id` (`"console"`): the element itself;
  - `(name, CSS selector)`: the first element matching it;
  - `(name, CSS selector, container)`: the closest ancestor of that element matching `container`,
    for a panel shown with its frame and title (`("geo", "#geo", "section")`).
- **Focus**: the views at the centre of the action are captured at every tick, the others one tick in
  four (`slow_every`), so that many open pages do not space the captures out. An image identical to
  the view's previous one is stored once.
- **Events** are reported by the driver, when it knows what happens; nothing is inferred from the
  images.

### The rushes

```
rushes-todo-20261028-155733/
  meta.json        viewport, scale, image size
  captures.jsonl   {t, view, file, url, label, panels}   one line per capture
  events.jsonl     {t, kind, ...fields}                  one line per event
  takes.jsonl      {t, name, file}                       the takes
  views/<view>/    the images
  takes/
  edit/            the images composed by the last editing
```

`t` is counted in seconds from the start of the shooting: it is the axis of the editor's timeline.

## Editing

```bash
nakyma edit <rushes> my.cut.yml                     # the video and the screenshots
nakyma edit <rushes> my.cut.yml --output videos/try # another basename
nakyma ui <rushes> my.cut.yml                       # the interactive editor
```

`--output` is the video's basename, or, for a cut of screenshots only, their directory. Paths in a
cut are relative to the directory the command is run in, `shots_dir` included.
`python -m nakyma` is the same command.

### The cut

```yaml
output: videos/todo                       # .mp4 and .webp are added (default: <rushes>/video)
formats: [mp4, webp]                      # png: the composed images as well
inset: {width: 0.42, corner: bottom-right}
timing: {caption: 3.5, round_frame: 0.25, last_caption: 5, blend: 0.4}

scenes:
  add:                                    # a kind of event starts a scene
    main: "page:{who}"                    # a view, filled with the event's fields
    inset: "page:{other}@list"            # view@panel
    caption: "{who} adds “{text}”"
    pace: progress
  done:
    main: "page:{who}"
    tiles: ["page:*"]                     # a pattern: every view of the family
    highlight: "page:{other}"
  end:
    main: "page:bob"
    caption: "{done} of {total} tasks done"
    pace: final

shots_dir: shots
shots:
  - {file: activity.png, take: activity}
  - {file: alice-list.png, view: "page:alice", at: end, after: 0.8, panel: list}
```

**Scenes.** Each kind of event having a rule in `scenes` starts a scene, which lasts until the next
such event; an event without a rule belongs to the scene in progress. A scene shows, for each
capture of its main view in that time:

| key | meaning |
|---|---|
| `main` | the view filling the image (required) |
| `inset` | a view shown in a corner, with a tab naming it; never enlarged, so that its text stays readable |
| `tiles` | instead of an inset, a **mosaic**: the main view smaller, and beside it one tile per view of the list (`*` matches several: `["page:*"]`), in the order the views appeared, the main view left out; a view gets its tile once it has been captured. A pattern's panel (`"page:*@list"`) is taken where the capture has it |
| `highlight` | the tile outlined, as `"page:{other}"` |
| `caption` | drawn at the bottom of the image (with tiles on the right: in the band under the main view) |
| `pace` | `event` (the scene lasts about `timing.caption` seconds), `progress` (its images scroll by: `timing.round_frame` each), `final` (`timing.last_caption`, then the last image stays) |

`{field}` in a view or a caption is replaced by the event's field: `page:{who}` designates the page
of whoever acts, whatever their name. A given scene is designated by its **kind and rank** (`kind`,
`index`), a screenshot by an **event and an offset** (`at`, `after`): both stay valid when the same
story is shot again.

**Mosaic** (`mosaic:`, the cut's layout of the tiles): `side: right` (default) puts them in a
column on the right, `side: bottom` in a row at the bottom; `slots` is how many the column or the
row holds before the tiles shrink (default 4 on the right, 6 at the bottom). A tile has the image's
proportions, so that `slots` tiles fill the column or the row: the main view keeps the rest
(three quarters of the width with 4 slots). A tile's label is cut to its width. A scene has an
inset or tiles, not both.

| `side: right` (default) | `side: bottom` |
|---|---|
| ![tiles on the right](../docs/images/recording_mosaic_right.png) | ![tiles at the bottom](../docs/images/recording_mosaic_bottom.png) |

**One scene** (`overrides:`): a rule applies to every scene of its kind; an override changes one,
the `index`-th scene of its kind (0 the first, in the order of the rushes):

```yaml
overrides:
  - {kind: open, index: 0, duration: 6}             # lasts 6 seconds, whatever its pace
  - {kind: add, index: 1, skip: true}               # left out, its time too
  - {kind: add, index: 2, offset: 1.5, inset: "page:bob@stats", corner: top-right, width: 0.35}
```

| key | meaning |
|---|---|
| `main`, `inset`, `caption`, `pace`, `tiles`, `highlight` | instead of the rule's (`inset: null`: no inset, `tiles: null`: no mosaic) |
| `offset` | seconds added to the scene's start (negative: earlier); the scene before ends there; scenes keep their order |
| `duration` | the scene's time in the video, shared by its images (at least one video frame each, 0.04 s) |
| `corner`, `width` | the inset's corner (`top-left`, `top-right`, `bottom-left`, `bottom-right`) and width, a share of the image's |
| `side`, `slots` | the mosaic's layout for this scene |
| `skip` | the scene is left out with its time; the scene before still ends where it began |

An unknown key, a kind without a rule, an index beyond the rushes' scenes or two overrides of one
scene stop the editing with a message.

**Screenshots** (`shots`, written into `shots_dir`, default `shots`): `{file, take: <name>}` copies a
take of the rushes; `{file, view, at: <kind of event>, index, after, panel}` extracts the view as it
was just after the `index`-th event of that kind (default 0), `after` seconds later (default 0), or
one of its panels.

**Timing** (`timing:`, seconds)

| key | meaning | default |
|---|---|---|
| `caption` | time an `event` scene lasts, shared by its images | `3.5` |
| `last_caption` | the same, for a `final` scene | `5.0` |
| `min_frame` | shortest time of one image | `0.25` |
| `round_frame` | time of one image in a `progress` scene | `0.25` |
| `progress_max` | longest time of a `progress` scene, however many its images: a long wait is squeezed | `8.0` |
| `end_hold` | extra time on the last image | `2.5` |
| `webp_width` | width of the WebP, in pixels (the MP4 keeps the captures' size) | `1080` |
| `blend` | share of each image's time spent fading into the next one: `0` cuts from image to image; images fade only within a scene, a new scene starts on a cut | `0.4` |

**The names are a convention between the driver and its cuts**: the views, the panels, the kinds
of events and their fields. A cut naming a view or a panel the rushes do not have stops with a
message listing those they have.

### The interactive editor

`nakyma ui <rushes> <cut>` opens a page of this machine only (`127.0.0.1`, a free port;
`--port` to choose it, `--no-browser` to only print its address):

- the **image** of the cut, as the export composes it, with ⏮ ◀ ▶ ▶| (or Home, ←, space, →): *play*
  shows each image of the video for its time, without the fade the export adds;
- the **video bar**: the scenes in the video's time, a click goes to one;
- the **timeline** of the rushes in their own time: the scenes (hatched when an override leaves one
  out), the events (large: they start a scene; small: no rule), and a track per view, a mark per
  capture (bright when the page changed). A click shows the cut's image at that moment, or on a
  view's track that view alone; a click on a scene selects it; the wheel zooms, a drag moves;
- the **scene** selected: its time in the rushes and in the video, its images, its main view, inset,
  tiles, outlined tile, caption, pace and the event's fields, in yellow what an override of that scene sets.

![the editor: scenes in mosaic, set for every scene of their kind](../docs/images/recording_editor.png)

The scene's settings are changed in the page, for **this scene** (an override: also its `offset`,
`duration`, the inset's `corner` and `width`, the tiles' `side` and `slots`) or for **every** scene
of its kind (the rule). Each change is checked by computing the plan again: a refused one (an offset
reversing two scenes, an unknown view…) shows its message and changes nothing. ↺ removes an
override's value; *Leave out this scene* skips it, *Bring it back* on its hatched mark undoes it.
Tiles are typed as a list separated by commas (`page:*, page:bob@stats`); given to a scene having
an inset, they replace it.

**Screenshots**: *Capture here* adds the view shown, whole or one of its panels, at the moment shown
(in the plan: the scene's main view at that image; on a view's track: that view), under the file
name proposed or typed; a take of the rushes is added under its name. The shot is written from the
event before that moment (`at`, `index`, `after`), so that it designates the same moment in another
shooting. Each screenshot is listed with its image, renamed in place, removed with ✕, and marked ◆
on the timeline; the directory (`shots_dir`) is set there too. A cut of screenshots only, without
scenes, opens as well.

![the editor: two screenshots taken, the second shown, its mark on the timeline](../docs/images/recording_editor_screenshots.png)

*Save* (or Ctrl+S) writes the cut's file with its comments and layout kept, the previous one in
`<cut>.bak`; *Revert* drops the unsaved changes. The header says whether the page is saved, has
unsaved changes, or the file changed on disk: saving then asks first. A change is sent with the
header `X-Nakyma-Editor: 1`, which a page of another site cannot send without the browser asking.

**Export** writes the video and the screenshots as `edit` does with the saved cut: the same files,
byte for byte (it waits for the cut to be saved). The *Export* section sets the video's path
(`output`) and its formats; a bar follows the images, then the encodings. The files written are
listed at the end, the video playable in the page; a failed export says why.

![the editor: the export done, its files and the video](../docs/images/recording_editor_export.png)

Without unsaved changes, the page reads the cut's file every 2 seconds: edit it elsewhere, save, the
page follows. A wrong cut is shown with its message, and the last plan stays.

## Outputs

- `<output>.mp4`: H.264, readable everywhere.
- `<output>.webp`: animated WebP, `webp_width` wide. Unlike an MP4 kept in a repository, GitHub
  shows it inside a page: `![a demo](videos/todo.webp)`.
- `<output>-frames/` (with `png`): the composed images.

## Writing a driver

Each application needs its own driver, but every driver follows the pattern of
`examples/todo/shoot.py`:

- start the application if it is local: a free port, its own process group
  (`start_new_session=True`), stopped by `os.killpg` in a `finally`; never look processes up by name;
- work in a directory with a neutral name when the application shows paths;
- declare a view per page, with a short name (`app`, `admin`, `page:alice`…), and panels for the
  parts a cut may show alone;
- report an event at the start of each step of the story, with fields the captions can use, then act
  and tick: about 3 ticks to let a change be seen, more on a moment to dwell on;
- a headless browser shows no mouse: draw a cursor in the page that moves to what is clicked if
  the clicks matter, and type text by a few letters per tick;
- choose an option of a `<select>` with `select_option` without clicking it (a click shows its
  native list over the page in the captures);
- after an action that reaches a server, wait for the page to be drawn again before the next one.

### Having a driver written by a coding agent

A coding agent that can read this directory can write the driver. Give it the prompt below, its
placeholders filled; it writes a driver and a cut, shoots, looks at the images and corrects until
the video tells the story.

```text
Write a driver that films a web application with Näkymä (nakyma/), and the cut that
edits its rushes into a video.

The application: <WHAT IT IS>
How to start it: <COMMAND, PORT OR URL, DATA IT NEEDS, HOW TO STOP IT>
The story to film, step by step: <e.g. "an empty list; add three tasks; mark one done; filter the
done tasks; delete one">
Video: <LENGTH, e.g. about 60 s>, captions in <LANGUAGE>, written to <OUTPUT BASENAME>.
Driver and cut: <PATHS>.

Read first:
- nakyma/README.md;
- nakyma/src/nakyma/shooting.py (Shooting: add_view, set_focus, event, tick, capture, take;
  panel_spec) and the docstring of nakyma/src/nakyma/editing.py (the cut's keys);
- nakyma/examples/todo/shoot.py and todo.cut.yml: a complete driver to follow.

The driver: a script with a PEP 723 header (playwright==1.63.0 and nakyma as a local editable
source, see "Prerequisites" in the README), run by `uv run`, importing nakyma (Shooting, log; nakyma.cli.edit_file to edit after the shooting) and
following the section "Writing a driver" of the README.

The cut: one rule per kind of event (main view, caption, pace: progress plays the images about as
shot, event shows a step in about 3.5 s, final ends on a longer caption); timing to keep the pace
close to the shooting (round_frame 0.3); overrides to shorten a long wait (duration).

Validate:
1. shoot with the cut "none", read events.jsonl, and look at images taken at the key moments of
   each step (captures.jsonl gives each image's time): every action visible, nothing hidden under
   the fold or a popup;
2. correct the driver and shoot again until every step reads right;
3. edit, then look at frames taken in the middle of each scene of the video: each caption over the
   step it describes;
4. report the length of the video, its events, and what was corrected on the way.
```

## When something goes wrong

- **`no capture of the view …` or `no panel …` when editing**: the cut names a view or a panel the
  rushes do not have; the message lists those they have.
- **`Executable doesn't exist at …/chromium_headless_shell-…`**: the driver's Playwright does not
  match the installed Chromium; install the browser (see *Prerequisites*).
- **Captions in a thin font**: neither DejaVu nor Liberation is installed (see *Prerequisites*).
