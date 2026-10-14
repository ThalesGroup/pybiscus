# Recording a session: rushes, videos and screenshots

`launch/doc/record_session.py` turns a session into a short video, for the documentation or a
presentation, and into the screenshots of the docs. It works in two times, as a film does:

1. **shoot**: the session runs and every page of it (the manager's, each agent's) is captured,
   with the events it goes through (an agent registers, a run is launched, round 3…). The result is
   a directory of **rushes**.
2. **edit**: a **cut** says what to make of the rushes: the scenes of a video (for each kind of
   event, the main view, an inset, a caption, a pace) and the screenshots to extract. Editing takes
   a few seconds and can be done again with another cut, without running the session again.

A session is shot in one of three ways: a **scenario** that runs it all (a manager and its agents
start on the machine, register, configure and launch the session), a **hierarchical scenario**
(a tree of sessions), or **`--attach`**, which follows a session someone runs.

The shooting and the editing are in `launch/doc/rushes/`, which knows nothing of Pybiscus: the
Pybiscus side (`record_session.py`) names the views, their panels and the events.

> This page follows the tool as it grows (see the end of the page).

## Prerequisites

- `uv`, and the repository's environment (`uv sync`).
- **ffmpeg** on the `PATH`, with its H.264 and WebP encoders (Debian, Ubuntu:
  `sudo apt install ffmpeg`).
- The **Chromium of Playwright 1.63.0**: the script pins this version, whose browser is the one
  installed in `~/.cache/ms-playwright` (`chromium-1243`). If it is missing:

  ```bash
  uv run --with playwright==1.63.0 playwright install chromium
  ```

  The script declares its own dependencies (Playwright, requests, PyYAML, Pillow) in its header:
  `uv run` installs them in a separate environment, not in the project's.

## Shooting

From the repository root:

```bash
uv run launch/doc/record_session.py shoot launch/doc/scenarios/mnist-session.yml
```

A scenario naming its cut (`cut:`) is edited right after: this command gives the rushes and
`docs/videos/mnist-session.mp4`.

| option | effect |
|---|---|
| `--rushes <dir>` | directory of the rushes (default `experiments/recordings/rushes-<scenario>-<date>`); it must be empty |
| `--cut <file>` | cut to edit right after, instead of the scenario's; `--cut none`: no editing |
| `--output <path>` | basename of the video, or directory of the screenshots, instead of the cut's |
| `--attach <manager URL>` | follow a running session instead of a scenario (see below) |
| `--max-duration <s>` | with `--attach`: stop after this many seconds |
| `--viewport <width>x<height>` | size of the captured pages, instead of the scenario's (`--viewport 1920x1080`) |
| `--scale <factor>` | pixel density of the captures (2: a 1440 × 900 page captured in 2880 × 1800, sharper text) |
| `--work-root <dir>` | where the working directory of the processes is created (default `/tmp`) |
| `--keep` | keep that working directory: logs of the manager and of each agent, run reports |

What happens with a scenario:
1. A working directory `/tmp/pybiscus-demo-XXXXXX` is created, with links to the plugin directories
   and to `datasets/`. The managers and the agents run there, so that their reports
   (`experiments/`) stay out of the repository. Its path appears in the server log shown by the
   pages: it is kept short and neutral on purpose, which is why `TMPDIR` is not used.
2. The managers, the agents and the Flower servers get free ports: the tool can run next to another
   Pybiscus installation, but **not next to a live session on the same machine** (it takes the CPU,
   the memory and, with `accelerator: auto`, the GPU).
3. A headless Chromium opens the pages, and the scenario plays the session as a person would. The
   pages being looked at (the manager's, and the one being acted on) are captured every
   `period`, the others every fourth time; an image identical to the previous one of its page is
   kept once.
4. When the runs have ended, the processes are stopped; the rushes stay.

A shooting fails, with a message, when an agent's configuration does not pass its check, when a run
does not succeed, or when the runs do not end within `timeout`.

**The rushes** (a directory; about 90 MB for the bundled scenario):

| file | content |
|---|---|
| `views/<view>/NNNNNN.png` | the captures of each page |
| `captures.jsonl` | one line per capture: time, view, file, the page's URL, its label, the position of its panels |
| `events.jsonl` | one line per event: time, kind and its fields (`{"t": 41.2, "kind": "launched", "name": "client-lyon", ...}`) |
| `takes/`, `takes.jsonl` | special captures asked by a scenario (a whole page, a panel after a click) |
| `meta.json` | viewport, scale, image size |
| `edit/` | the images composed by the last editing |

## Editing

```bash
uv run launch/doc/record_session.py edit <rushes> launch/doc/scenarios/mnist-session.cut.yml
uv run launch/doc/record_session.py edit <rushes> my.cut.yml --output docs/videos/try
```

### The cut

```yaml
output: docs/videos/mnist-session         # .mp4 and .webp are added (default: <rushes>/video)
formats: [mp4, webp]                      # png: the composed images as well
inset: {width: 0.42, corner: bottom-right}
timing: {caption: 3.5, round_frame: 0.25, last_caption: 5, blend: 0.4}

scenes:
  registered:
    main: "agent:{name}"
    inset: "manager@geo"
    caption: "2 · Agent {name} registers ({role}, {location})"
  round:
    main: manager
    inset: "agent:{turn}@console"
    caption: "5 · Federated training: round {round} / {rounds}"
    pace: progress
  finished:
    main: manager
    caption: "6 · Session finished: test accuracy {accuracy} after {rounds} rounds"
    pace: final

shots_dir: docs/images
shots:
  - {file: hier_core_relays.png, view: "manager:core", at: relays}
  - {file: hier_cycles.png, take: core-cycles}
```

**Scenes.** Each kind of event having a rule in `scenes` starts a scene, which lasts until the next
such event; an event without a rule belongs to the scene in progress. A scene shows, for each
capture of its main view in that time:

| key | meaning |
|---|---|
| `main` | the view filling the image (required) |
| `inset` | a view shown in a corner, with a tab naming it; never enlarged, so that its text stays readable |
| `caption` | drawn at the bottom of the image |
| `pace` | `event` (the scene lasts about `timing.caption` seconds), `progress` (its images scroll by: `timing.round_frame` each), `final` (`timing.last_caption`, then the last image stays) |

`{field}` in a view or a caption is replaced by the event's field. The views:

| view | what it shows |
|---|---|
| `manager` (`manager:<bouquet>` in a hierarchical scenario) | a session manager's page |
| `agent:<name>` | the agent's tab: its registration form, its waiting page, its configuration form (check, launch), then its run monitor |
| `session-form` | the server's session form, while it is filled |
| `<view>@<panel>` | a panel of a view: `manager@geo` (the map), `manager@nodes` (the agents and their states), `manager@accChart` (the accuracy curves), `manager@cyclesChart` (the cycles), `agent:<name>@console` (the run's log) |

The events, and their fields:

| shot by | events |
|---|---|
| a scenario | `empty`; `registered`, `launched` (`name`, `role`, `location`); `configured` (`rounds`); `started`; `round` (`round`, `rounds`, `turn`: the client whose turn it is in the inset, one per round); `finished` (`accuracy`, `rounds`) |
| `--attach` | `attached` or `joined` (`count`: agents registered); `registered` (`name`, `role`, `location`); `started`; `validated`, `executing` (`name`); `round` (`round`, `rounds`, `of_rounds`: " / 5", or empty when unknown); `failed` (`name`, `state`); `finished` (`accuracy`); `dropped`; `interrupted`; `lost` (the manager no longer answers: the shooting stops, what it has is edited) |
| a hierarchical scenario | `registered`; `relays`; `session-form` (`bouquet`); `form` (`name`); `round` (`round`, `rounds`, `turn`: the lower bouquet whose turn it is); `end`; `tab` (`tab`) |

**Screenshots** (`shots`, written into `shots_dir`): `{file, take: <name>}` copies a take of the
rushes; `{file, view, at: <kind of event>, index, panel}` extracts the view as it was just after
the `index`-th event of that kind (default 0), or one of its panels.

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

The defaults give a 1-minute video for the bundled scenario; `timing: {caption: 2.2, round_frame: 0.12,
last_caption: 4, blend: 0}` a brisker 40-second one.

## Scenarios

### A simple session

`launch/doc/scenarios/mnist-session.yml` (one server, two clients, 5 rounds; about 2 minutes):

| key | meaning | default |
|---|---|---|
| `cut` | the cut edited right after the shooting | none |
| `viewport`, `scale` | size and pixel density of the pages | `1440 × 900`, `1` |
| `inset_viewport` | the window of an agent's tab once its run is launched, narrow so that its run monitor stays readable as an inset | `760 × 470` |
| `period` | pause between two captures, in seconds (the captures themselves take a few tenths) | `0.35` |
| `manager` | `bouquet` (the session's name), `location`, `geo` (`[latitude, longitude]`) | required |
| `agents` | `name`, `role` (`server` or `client`), `location`, `geo`; the first server holds the session | required |
| `organisation` | organisation declared by every agent | `pybiscus-demo` |
| `session.options` | options chosen in the server's session form, by their labels (`model: MNIST CNN`); `" "` selects an optional section (`num_rounds`, `data_partition`) | required |
| `session.values` | values of the form's fields; `num_rounds` is required | required |
| `plugin_manifests` | manifests given to the agents, relative to the repository | the bundled one |
| `timeout` | seconds allowed for the runs, once launched | `1800` |

Each agent registers through its own registration form, then its tab follows it to its run
monitor. With 3 tabs, the bundled scenario takes about 6 GB of memory on top of the system's.

### A hierarchical session

`launch/doc/scenarios/hierarchical-core-edges.yml` runs the core and two edges of
[hierarchical-session.md](hierarchical-session.md); its cut writes the screenshots of its
walkthrough into `docs/images` (check them with `git diff` before committing).

| key | meaning |
|---|---|
| `kind` | `hierarchical` |
| `managers` | one entry per bouquet: `bouquet`, `location`, `geo`, and `upper` (the bouquet above; none for the root) |
| `agents` | `name`, `role`, `bouquet`; a relay has `relay_for: <lower bouquet>` and is designated in its manager's page |
| `session` | `options` and `values` of the root's session form |
| `lower_session` | `options` and `values` added to each lower level's form, on top of what its upper level imposes and locks |
| `plugin_manifests` | the relay and `upper_level_link` need the hierarchical plugins |
| `viewport`, `form_viewport` | the managers' pages, the forms |
| `takes` | `name`, `at` (`registered`, `relays`, `session-form:<bouquet>`, `form:<agent>`, `end`), `view` (with `@<panel>`), `full_page`, `tab` (a tab of the manager's middle panel to open first: `cycles`, `constraints`) |

Its other cut, `hierarchical-core-edges.video.cut.yml`, makes a video of the same rushes: the tree
on the core's map, the relays, the session forms, the launches, then the rounds on the core's page
with, in the inset, the accuracy curve of the edge whose turn it is, and the cycles at the end:

```bash
uv run launch/doc/record_session.py edit <rushes> launch/doc/scenarios/hierarchical-core-edges.video.cut.yml
```

Its events add `round` (`round`, `rounds`, `turn`: the edge in the inset) and `tab` (`tab`: a tab
a take opened, the pages being captured after it). The agents register by the API (no tab each,
for memory) and their tab is closed once launched.
**Memory**: its 3 managers, 9 agents (6 mnist runs) and the browser reach about 15.5 GB on a 16 GB
machine; run it alone.

## Outputs

- `<output>.mp4`: H.264, readable everywhere (about 2 MB for the bundled scenario at
  `1440 × 900`; at `1920 × 1080` with `scale: 2`, a 3840 × 2160 video about four times heavier
  per second).
- `<output>.webp`: animated WebP, `webp_width` wide (about 1.8 MB). Unlike an MP4 kept in the
  repository, GitHub shows it inside a page: `![a mnist session](videos/mnist-session.webp)`.
- `<output>-frames/` (with `png`): the composed images.

**Choosing the size.** The manager's page follows the width of the window: below about 1200 pixels
its panels narrow and the logs become hard to read in a video. `1440 × 900` and `1920 × 1080` suit
it; `scale: 2` is for a large screen or a presentation.

`docs/videos/` is kept out of git for now (its `.gitignore`): every video weighs in the
repository's history forever, so only short ones should be versioned, once chosen.

## When something goes wrong

- **An agent's configuration does not pass its check**: shoot again with `--keep` and read
  `agent_<name>.log` in the working directory; check the scenario's `session.options` against the
  labels of the server's session form.
- **`Executable doesn't exist at …/chromium_headless_shell-…`**: the Playwright of the script does
  not match the installed Chromium; install the browser (see *Prerequisites*).
- **The runs do not end**: `timeout` is reached; with `--keep`, the agents' logs and the reports
  in `experiments/` tell where the run stopped.
- **`no capture of the view …` or `no panel …` when editing**: the cut names a view or a panel the
  rushes do not have; the message lists those they have.

## Recording a session you run yourself

**With `--attach`**, the tool follows a session driven by hand, from its manager:

```bash
uv run launch/doc/record_session.py shoot --attach http://localhost:5555 --output docs/videos/my-session
```

It drives nothing and starts nothing: it opens the manager's page in a headless browser, reads the
manager's state (`/pybiscus-session/agents`) between two captures, and turns what happens into
events. It stops by itself when every launched run has ended (or when the session is dropped), at
`--max-duration`, or on **Ctrl+C**; the rushes are then edited with
`launch/doc/scenarios/attach.cut.yml`, unless `--cut` gives another cut.
It can be started before or during the session. Started during it, it shows only what happens from
then on (`joined` first), but the page still shows the whole session so far: it reads the logs, the
metrics and the vignettes from their beginning.

- Without `--output`, the video goes into the rushes (`<rushes>/video.mp4`). A scenario file can
  still be given, for its `viewport`, `scale`, `period` and `cut`.
- An agent going through a step faster than a capture (a few tenths of a second) gets no event for
  it: its next state's follows.
- A manager reachable beyond the loopback requires its administration token: give the URL it
  printed when it started, `--attach 'http://host:5555?token=…'`.
- The recorder's page and the pages of the people following the session do not take anything from
  each other: each page reads the manager's logs, metrics and vignettes from its own position.

**With a screen recorder**, the session can also be recorded from your own screen:
[OBS Studio](https://obsproject.com/) (a *browser source* per page lets a scene show the manager
and agents side by side), or on Windows the Xbox Game Bar (`Win` + `Alt` + `R`). Captions and
time-lapse are then added while editing (Clipchamp, Shotcut, Kdenlive, ffmpeg).

**Planned** (not available yet):
- an interactive editor writing the cut: a timeline of the events, a track per view, the scenes, a
  preview of the composed image;
- side by side views (a mosaic), as an alternative to a main view and an inset; the inset's corner
  per scene;
- the agents' run monitors with `--attach`;
- a recording started by the session manager itself, with captions taken from its events;
- a record button in the manager's page, recording the tab from the browser.
