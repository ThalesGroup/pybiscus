# Recording a session: time-lapse videos

`launch/doc/record_session.py` records a session as seen from the session manager's page and
turns it into a short time-lapse video, for the documentation or a presentation. It works in two
ways:
- **with a scenario**, it runs the whole session itself: a manager and its agents start on the
  machine, a *scenario* file says which agents register, how the server's session is configured
  and what the captions say;
- **with `--attach`**, it records a session someone runs, from its manager, without driving it
  (see [Recording a session you run yourself](#recording-a-session-you-run-yourself)).

The video shows the agents appearing on the map, the runs being launched, then the accuracy and
loss curves and the model vignettes filling in round after round.

> This page follows the tool as it grows: views of the agents' pages, hierarchical sessions and a
> recording started by the manager itself are planned (see the end of the page).

## Prerequisites

- `uv`, and the repository's environment (`uv sync`).
- **ffmpeg** on the `PATH`, with its H.264 and WebP encoders (Debian, Ubuntu:
  `sudo apt install ffmpeg`).
- The **Chromium of Playwright 1.63.0**: the script pins this version, whose browser is the one
  installed in `~/.cache/ms-playwright` (`chromium-1243`). If it is missing:

  ```bash
  uv run --with playwright==1.63.0 playwright install chromium
  ```

  The script declares its own dependencies (Playwright, requests, PyYAML) in its header: `uv run`
  installs them in a separate environment, not in the project's.

## Recording

From the repository root:

```bash
uv run launch/doc/record_session.py launch/doc/scenarios/mnist-session.yml
```

| option | effect |
|---|---|
| `--output <path>` | basename of the outputs, instead of the scenario's `output` |
| `--attach <manager URL>` | record a running session instead of a scenario (see below) |
| `--max-duration <s>` | with `--attach`: stop recording after this many seconds |
| `--assemble <frames dir>` | only assemble the images of an earlier recording, with the scenario's `output`, `formats` and `timing` (see below) |
| `--viewport <width>x<height>` | size of the captured page, instead of the scenario's `viewport` (`--viewport 1920x1080`) |
| `--scale <factor>` | pixel density of the captures, instead of the scenario's `scale` (see below) |
| `--work-root <dir>` | where the working directory is created (default `/tmp`) |
| `--keep` | keep the working directory: logs of the manager and of each agent, frames, run reports |

What happens:
1. A working directory `/tmp/pybiscus-demo-XXXXXX` is created, with links to the plugin directories
   and to `datasets/`. The manager and the agents run there, so that their reports
   (`experiments/`) stay out of the repository. Its path appears in the server log shown by the
   page: it is kept short and neutral on purpose, which is why `TMPDIR` is not used.
2. The manager, the agents and the Flower server get free ports: the tool can run next to another
   Pybiscus installation, but **not next to a live session on the same machine** (it takes the CPU,
   the memory and, with `accelerator: auto`, the GPU).
3. The manager's page and a tab per agent open in a headless Chromium. Each agent registers
   through its own registration form, as a person does; the server's session form is filled, then
   each agent checks its configuration and launches its run, which its tab then follows (run
   monitor). The video is **directed**: each step has a main view and, often, an inset, chosen by
   the scenario's `direction` (see [Direction](#direction-main-view-and-inset)), and a caption.
4. When every agent's run has ended (`/run/status`), the processes are stopped and the frames are
   assembled: each caption stays about 2 seconds, the rounds scroll by, the last image stays.

A run fails, with a message, when an agent's configuration does not pass its check, when a run
does not succeed, or when the runs do not end within `timeout`.

The bundled scenario, a simple mnist session with one server and two clients over 5 rounds,
takes about 2 minutes and gives a 1-minute video. With its tabs, it takes about 6 GB of memory on
top of the system's.

## The scenario file

```yaml
output: docs/videos/mnist-session     # .mp4 and .webp are added
formats: [mp4, webp]                  # png: the frames as well
viewport: {width: 1440, height: 900}
period: 0.35                          # seconds between two captures, on top of the capture itself

manager: {bouquet: demo, location: paris-hq, geo: [48.8566, 2.3522]}
agents:
  - {name: server, role: server, location: paris-hq, geo: [48.8566, 2.3522]}
  - {name: client-lyon, role: client, location: lyon-lab, geo: [45.7640, 4.8357]}
  - {name: client-lille, role: client, location: lille-lab, geo: [50.6292, 3.0573]}

session:                              # applied to the server's session form
  options: {model: MNIST CNN, num_rounds: " ", data_partition: " "}
  values: {data: Mnist, num_rounds: "5"}

captions:
  empty: "1 · An empty session: the manager waits for its agents"
  registered: "2 · Agent {name} registers ({role}, {location})"
  configured: "3 · The server's session is configured: MNIST CNN, {rounds} rounds, data split between the clients"
  started: "3 · The session starts: each agent receives its form, checks it and launches"
  launched: "4 · {name}: configuration checked, run launched"
  round: "5 · Federated training: round {round} / {rounds}"
  finished: "6 · Session finished: test accuracy {accuracy} after {rounds} rounds"
```

| key | meaning | default |
|---|---|---|
| `output` | basename of the outputs, relative to the directory the tool is run from | required (or `--output`) |
| `formats` | among `mp4`, `webp`, `png` (`png`: the frames, in `<output>-frames/`) | `[mp4, webp]` |
| `viewport` | size of the captured page, in pixels | `1440 × 900` |
| `scale` | pixel density of the captures: the page keeps the viewport's layout, its pixels are multiplied (2: a 1440 × 900 page captured in 2880 × 1800, sharper text) | `1` |
| `period` | pause between two captures, in seconds (a capture itself takes a few tenths) | `0.35` |
| `manager` | `bouquet` (the session's name), `location`, `geo` (`[latitude, longitude]`) | required |
| `agents` | one entry per agent: `name`, `role` (`server` or `client`), `location`, `geo`; the first server holds the session | required |
| `organisation` | organisation declared by every agent | `pybiscus-demo` |
| `session.options` | options chosen in the server's session form, by their labels (`model: MNIST CNN`); `" "` selects an optional section (`num_rounds`, `data_partition`) | required |
| `session.values` | values of the form's fields; `num_rounds` is required, and gives `{rounds}` | required |
| `captions` | the seven captions below | required |
| `hold` | number of captures per caption: `empty`, `registered`, `configured`, `started`, `launched`, `finished` | 8, 5, 6, 3, 5, 12 |
| `direction` | main view and inset of each step, see below | see below |
| `inset` | `width` (largest share of the image's width), `corner` (`bottom-right`, `bottom-left`, `top-right`, `top-left`), `viewport` (an agent's tab once its run is launched) | `0.42`, `bottom-right`, `760 × 470` |
| `timing` | durations in the video, see below | |
| `timeout` | seconds allowed for the runs, once launched | `1800` |

### Direction: main view and inset

Each step shows a *main view*, which fills the image, and possibly an *inset* in a corner, with a
tab naming what it shows. The views:

| view | what it shows |
|---|---|
| `manager` | the session manager's page |
| `agent:<name>` | the agent's tab: its registration form, then its waiting page, its configuration form (check, launch), then its run monitor |
| `session-form` | the server's session form, while it is filled |
| `<view>@<element id>` | the panel holding that element: `manager@geo` (the map), `manager@nodes` (the agents and their states), `agent:<name>@console` (the run's log) |

`{agent}` stands for the agent of the step, `{clients}` for the client whose turn it is during the
rounds: the clients take turns, one per round. The defaults, which a scenario's `direction`
replaces step by step:

```yaml
direction:
  empty:      {main: manager}
  registered: {main: "agent:{agent}", inset: "manager@geo"}
  configured: {main: session-form, inset: "manager@nodes"}
  started:    {main: manager}
  launched:   {main: "agent:{agent}", inset: "manager@nodes"}
  round:      {main: manager, inset: "agent:{clients}@console"}
  finished:   {main: manager}
```

An inset is never enlarged beyond its own size, so that its text stays readable; an agent's tab
gets the narrower `inset.viewport` once its run is launched, since from then on it is only an
inset. The caption is drawn on the composed image, at the same place whatever the main view.

**Captions**

| caption | shown | variables |
|---|---|---|
| `empty` | before any agent registers | |
| `registered` | after each agent's registration | `{name}`, `{role}`, `{location}` |
| `configured` | when the server's session form is about to be filled | `{rounds}` |
| `started` | once the manager has accepted the session | |
| `launched` | after each agent has checked its configuration and launched its run | `{name}`, `{role}`, `{location}` |
| `round` | during the training, updated with the round shown by the page | `{round}`, `{rounds}` |
| `finished` | at the end | `{accuracy}` (the test accuracy shown by the page), `{rounds}` |

**Timing** (`timing:`, seconds)

| key | meaning | default |
|---|---|---|
| `caption` | time a caption stays on screen, shared by its captures | `3.5` |
| `last_caption` | the same, for the last caption | `5.0` |
| `min_frame` | shortest time of one capture | `0.25` |
| `round_frame` | time of one capture during the rounds and the waits | `0.25` |
| `progress_max` | longest time of a round or of a wait, however many its captures: a long wait is squeezed | `8.0` |
| `end_hold` | extra time on the last image | `2.5` |
| `webp_width` | width of the WebP, in pixels (the MP4 keeps the viewport's size times `scale`) | `1080` |
| `blend` | share of each image's time spent fading into the next one: `0` cuts from image to image, `0.4` fades over the last 40 %; a change of main view stays a cut | `0.4` |

**A faster, slower or smoother video.** The captures are 0.6 to 0.9 s of session apart: `blend`
fades each into the next instead of jumping (`0` for cuts; up to `0.7`–`0.8` for longer fades).
`caption` and `round_frame` set how long the steps and the rounds last: the defaults give a
1-minute video for the bundled scenario; `timing: {caption: 2.2, round_frame: 0.12, last_caption: 4,
blend: 0}` gives a brisker 40-second one. To try such settings
without running the session again, keep the images (`--keep`, or `png` in `formats`) and assemble
them again, which takes a few seconds:

```bash
uv run launch/doc/record_session.py my-timing.yml --assemble /tmp/pybiscus-demo-XXXXXX/frames --output docs/videos/try
```

where `my-timing.yml` holds only the keys to change (`timing:`, `formats:`).

## Outputs

- `<output>.mp4`: H.264, at the viewport's size times `scale`, readable everywhere (about 2 MB
  for the bundled scenario at `1440 × 900`; at `1920 × 1080` with `scale: 2`, a 3840 × 2160 video,
  about four times heavier per second).
- `<output>.webp`: animated WebP, 1080 pixels wide (about 1.8 MB). Unlike an MP4 kept in the
  repository, GitHub shows it inside a page: `![a mnist session](videos/mnist-session.webp)`.
- `<output>-frames/` (with `png`): every capture and `captions.tsv`, which gives the kind
  (`event`, `progress`, `final`) and the caption of each one.

**Choosing the size.** The manager's page follows the width of the window: below about 1200 pixels
its panels narrow and the logs become hard to read in a video. `1440 × 900` and `1920 × 1080` suit
it; `scale: 2` is for a large screen or a presentation, the WebP stays `webp_width` wide.

`docs/videos/` is kept out of git for now (its `.gitignore`): every video weighs in the
repository's history forever, so only short ones should be versioned, once chosen.

## When something goes wrong

- **An agent's configuration does not pass its check**: run again with `--keep` and read
  `agent_<name>.log` in the working directory; check the scenario's `session.options` against the
  labels of the server's session form.
- **`Executable doesn't exist at …/chromium_headless_shell-…`**: the Playwright of the script does
  not match the installed Chromium; install the browser (see *Prerequisites*).
- **The runs do not end**: `timeout` is reached; with `--keep`, the agents' logs and the reports
  in `experiments/` tell where the run stopped.

## Recording a session you run yourself

**With `--attach`**, the tool follows a session driven by hand, from its manager:

```bash
uv run launch/doc/record_session.py --attach http://localhost:5555 --output docs/videos/my-session
```

It drives nothing and starts nothing: it opens the manager's page in a headless browser, reads the
manager's state (`/pybiscus-session/agents`) between two captures, and captions what happens: the
agents registering, the session starting, each agent's configuration checked and run launched, the
rounds, a run that fails. It stops by itself when every launched run has ended (or when the session
is dropped), at `--max-duration`, or on **Ctrl+C**; the captures are then assembled as usual.
It can be started before or during the session. Started during it, it captions only what
happens from then on (`joined` first), but the page still shows the whole session so far: it
reads the logs, the metrics and the vignettes from their beginning.

- Without a scenario, the outputs go to `experiments/recordings/session-<date>-<time>`, unless
  `--output` is given. A scenario file can still be given, for its `output`, `formats`,
  `viewport`, `scale`, `period`, `hold`, `timing` and its `captions`, which then replace these
  (`--viewport` and `--scale` also apply without a scenario):

  | caption | shown | variables |
  |---|---|---|
  | `waiting` | before the runs, between the events | `{count}` (agents registered) |
  | `registered` | when an agent registers | `{name}`, `{role}`, `{location}` |
  | `started` | when the session starts | |
  | `joined` | at the start of the recording, when the session is already running | `{count}` (agents registered) |
  | `validated` | when an agent's configuration has been checked | `{name}` |
  | `executing` | when an agent's run is launched | `{name}` |
  | `round` | during the training | `{round}`, `{of_rounds}` (" / 5", or empty when the manager does not know the number of rounds) |
  | `failed` | when a run fails or is stopped | `{name}`, `{state}` |
  | `finished` | when every launched run has ended | `{accuracy}` |
  | `dropped` | when the session is dropped | |
  | `interrupted` | at `--max-duration` or Ctrl+C | |

  An agent going through a step faster than a capture (a few tenths of a second) gets no caption
  for it: its next state's caption follows.
- A manager reachable beyond the loopback requires its administration token: give the URL it
  printed when it started, `--attach 'http://host:5555?token=…'`.
- The recorder's page and the pages of the people following the session do not take anything from
  each other: each page reads the manager's logs, metrics and vignettes from its own position.

**With a screen recorder**, the session can also be recorded from your own screen:
[OBS Studio](https://obsproject.com/) (a *browser source* per page lets a scene show the manager
and agents side by side), or on Windows the Xbox Game Bar (`Win` + `Alt` + `R`). Captions and
time-lapse are then added while editing (Clipchamp, Shotcut, Kdenlive, ffmpeg).

**Planned** (not available yet):
- side by side views (a mosaic), as an alternative to the direction; agents' run monitors with
  `--attach`;
- scenarios for hierarchical sessions;
- a recording started by the session manager itself, with captions taken from its events;
- a record button in the manager's page, recording the tab from the browser.
