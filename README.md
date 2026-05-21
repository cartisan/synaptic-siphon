# synaptic-siphon

Two terminal CLIs that capture short voice memos and stitch random
ones together into a dreamy, effected "story":

- **`siphon-record`** — hold SPACE to record audio; on release, leading
  and trailing silence are trimmed and the take is split into 10-second
  WAV chunks in `recordings/`. ESC quits.
- **`siphon-generate`** — picks 6–12 random clips from `recordings/`,
  crossfades them together, layers a synthesized heart-thump and
  bubbling sounds on top, applies an underwater low-pass filter, and
  writes the result as an MP3 in `stories/`. Designed to be run from
  cron.

All effect parameters (heart volume / BPM / pitch, bubble density,
low-pass cutoff, etc.) live in `config.toml` so you can experiment
with the mix.

## Install — macOS

```bash
# 1. uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. ffmpeg (used by pydub for MP3 encoding) and portaudio (sounddevice backend)
brew install ffmpeg portaudio

# 3. clone & sync
git clone <this-repo> synaptic-siphon
cd synaptic-siphon
uv sync
```

**One-time permission:** the recorder uses `pynput` to detect SPACE
press *and release*, which on macOS requires Accessibility permission
for your terminal. The first time you run `siphon-record` macOS will
prompt you; otherwise add your terminal app manually under
**System Settings → Privacy & Security → Accessibility**. The
microphone permission prompt for `sounddevice` also appears on first
run.

## Install — Ubuntu Linux

```bash
# 1. uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. system audio + MP3 encoder
sudo apt update
sudo apt install -y ffmpeg libportaudio2 portaudio19-dev

# 3. clone & sync
git clone <this-repo> synaptic-siphon
cd synaptic-siphon
uv sync
```

**Display server note:** `pynput` reads keyboard events from X11. On
Wayland it usually works under XWayland, but if the recorder doesn't
see your key presses, either log in to an X11 session or add yourself
to the `input` group so `pynput` can use its `/dev/input` backend:

```bash
sudo usermod -aG input "$USER"  # log out and back in afterwards
```

## Run the recorder

```bash
uv run siphon-record
```

Hold SPACE while you speak; release to save. The recorder trims the
silence on either end and writes one or more 10-second WAVs into
`recordings/`. Press ESC to quit.

## Run the generator

```bash
uv run siphon-generate
```

Writes one MP3 into `stories/` and prints its path. Exits non-zero if
you don't have at least `min_clips` recordings yet.

## Schedule the generator (cron)

Cron has a minimal `PATH`, so use absolute paths for both `uv` and the
project directory:

```bash
which uv     # e.g. /Users/leonid/.local/bin/uv or /home/leonid/.local/bin/uv
pwd          # absolute project path
crontab -e
```

Example: run every 4 hours and log to `/tmp/synaptic-siphon.log`.

```cron
0 */4 * * * cd /absolute/path/to/synaptic-siphon && /absolute/path/to/uv run siphon-generate >> /tmp/synaptic-siphon.log 2>&1
```

This works the same on macOS (user crontab via `crontab -e`) and on
Ubuntu. On macOS, cron also needs **Full Disk Access** if the project
or output directories live under `~/Documents`, `~/Desktop`, etc.

## Tweaking the effects

Edit `config.toml`:

| Section                 | Knob              | Effect                                                        |
|-------------------------|-------------------|---------------------------------------------------------------|
| `[generator.heart]`     | `volume`          | 0.0 disables the thump entirely.                              |
|                         | `bpm`             | Beats per minute. Lower = bigger creature.                    |
|                         | `fundamental_hz`  | Pitch of each thump.                                          |
|                         | `beat_decay`      | Tail length of each thump in seconds.                         |
| `[generator.bubbles]`   | `volume`          | 0.0 disables bubbles.                                         |
|                         | `density`         | Average bursts per second.                                    |
|                         | `brightness_hz`   | Top of each bubble's rising chirp.                            |
| `[generator.lowpass]`   | `cutoff_hz`       | Underwater feel. Push toward 20000 to effectively disable.    |
|                         | `order`           | Butterworth order (steeper rolloff at higher values).         |
| `[generator]`           | `crossfade_ms`    | Length of the crossfade between recordings.                   |
|                         | `min_clips` / `max_clips` | Range of recordings drawn per story.                  |
|                         | `random_seed`     | `0` = nondeterministic; any other int reproduces a mix.       |

The recorder's silence-trim threshold and chunk size live under
`[recorder]` in the same file.
