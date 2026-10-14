# Recording a session: time-lapse videos

`launch/doc/record_session.py` records a session as seen from the session manager's page and
turns it into a short time-lapse video, for the documentation or a presentation. It runs the whole
session itself: a manager and its agents start on the machine, a *scenario* file says which agents
register, how the server's session is configured and what the captions say. The video shows the
agents appearing on the map, the runs being launched, then the accuracy and loss curves and the
model vignettes filling in round after round.

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
3. The manager's page opens in a headless Chromium and is captured with the current caption:
   the empty session, each agent registering, the server's session being configured and started,
   each agent checking its configuration and launching its run, every round, the end.
4. When every agent's run has ended (`/run/status`), the processes are stopped and the frames are
   assembled: each caption stays about 2 seconds, the rounds scroll by, the last image stays.

A run fails, with a message, when an agent's configuration does not pass its check, when a run
does not succeed, or when the runs do not end within `timeout`.

The bundled scenario, a simple mnist session with one server and two clients over 5 rounds,
takes about 2 minutes and gives a 40-second video.

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
| `period` | pause between two captures, in seconds (a capture itself takes a few tenths) | `0.35` |
| `manager` | `bouquet` (the session's name), `location`, `geo` (`[latitude, longitude]`) | required |
| `agents` | one entry per agent: `name`, `role` (`server` or `client`), `location`, `geo`; the first server holds the session | required |
| `organisation` | organisation declared by every agent | `pybiscus-demo` |
| `session.options` | options chosen in the server's session form, by their labels (`model: MNIST CNN`); `" "` selects an optional section (`num_rounds`, `data_partition`) | required |
| `session.values` | values of the form's fields; `num_rounds` is required, and gives `{rounds}` | required |
| `captions` | the seven captions below | required |
| `hold` | number of captures per caption: `empty`, `registered`, `configured`, `started`, `launched`, `finished` | 8, 5, 4, 3, 3, 12 |
| `timing` | durations in the video, see below | |
| `timeout` | seconds allowed for the runs, once launched | `1800` |

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

The rounds are recognised in the video by the beginning of the `round` caption, up to its first
`{`: it must differ from the other captions' beginning.

**Timing** (`timing:`, seconds)

| key | meaning | default |
|---|---|---|
| `caption` | time a caption stays on screen, shared by its captures | `2.2` |
| `last_caption` | the same, for the last caption | `4.0` |
| `min_frame` | shortest time of one capture | `0.25` |
| `round_frame` | time of one capture during the rounds | `0.12` |
| `end_hold` | extra time on the last image | `2.5` |
| `webp_width` | width of the WebP, in pixels (the MP4 keeps the viewport's) | `1080` |

## Outputs

- `<output>.mp4`: H.264, at the viewport's size, readable everywhere (about 0.8 MB for the
  bundled scenario).
- `<output>.webp`: animated WebP, 1080 pixels wide (about 0.5 MB). Unlike an MP4 kept in the
  repository, GitHub shows it inside a page: `![a mnist session](videos/mnist-session.webp)`.
- `<output>-frames/` (with `png`): every capture and `captions.tsv`, which gives the caption of
  each one.

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

The tool runs its own session. To record one driven by hand in a browser, use a screen recorder
for now: [OBS Studio](https://obsproject.com/) (a *browser source* per page lets a scene show the
manager and agents side by side), or on Windows the Xbox Game Bar (`Win` + `Alt` + `R`). Captions
and time-lapse are then added while editing (Clipchamp, Shotcut, Kdenlive, ffmpeg).

**Planned** (not available yet):
- several views in one video: the agents' forms and run monitors with the manager, either one view
  at a time following the steps, or side by side;
- scenarios for hierarchical sessions;
- `--attach <manager URL>`: record a session started by hand, without driving it;
- a recording started by the session manager itself, with captions taken from its events;
- a record button in the manager's page, recording the tab from the browser.
