# Architecture

Pumpkin's Thumb It turns video files into a pack of images in a `scr/` folder next to the videos. Two independent implementations produce the same pack:

- **Windows GUI**: single-file Tkinter scripts at the repo root (`Pumpkin’s Thumb It 5.2.py`, plus the legacy `Pumpkin’s Thumb It v5.py`).
- **Linux CLI**: the `thumb_it` package in `linux/`, installed as the `thumb-it` command.

They share no code. The CLI is a port of the 5.x layout built on Pillow and FFmpeg, with no Tkinter, OpenCV or NumPy.

## The output pack

| File | Format | Content |
| --- | --- | --- |
| `sheet_<video>.png` | PNG | 1492 px wide sheet: media-info header, 16 small and 5 large rounded thumbnails |
| `center1` to `center5` | WebP or AVIF | The same sheet with the 5 large slots playing short clips; first 5 videos per folder |
| `centerlongest_<folder>` | WebP or AVIF | 960×540 clip from the middle of the folder's longest video |
| `screen.png` | PNG | One frame from the middle of the longest video |

## Rendering pipeline (both implementations)

1. **Probe** the video with FFprobe (duration, resolution, codecs, bitrates) for the header and to pick timestamps.
2. **Layout**: 21 slots in fixed positions below a header (6 small, 1 big, 4 small, 1 big, 3 big, 6 small). The header is 146 px tall, or taller when the logo is.
3. **Choose times** for each slot: evenly spread, with jitter, an edge guard, a minimum gap between thumbnails, and a seed derived from the video path so the choice is reproducible.
4. **Grab frames** with FFmpeg, scaled and padded to the slot size.
5. **Composite** each frame into its slot with a rounded mask and shadow, then save the PNG sheet.
6. **Animate**: the timeline is split into 25 buckets, 5 per animated sheet. Each of the 5 big slots plays a clip from its own bucket, and the other slots stay static. Overlap with the stills is avoided.
7. **Encode** the frames, searching for the highest quality that fits the size limit (see below).

## Encoding and size cap

`_fit_webp_quality` (GUI) and `Renderer.fit_animation` (CLI) share one strategy: encode at the starting quality; if it is over the limit, encode at the floor; if the floor fits, binary-search between them and keep the highest quality that fits. This replaced a loop that dropped quality in steps of 10.

| Format | Start | Floor | Speed setting |
| --- | --- | --- | --- |
| WebP | profile quality (85/75/70), capped at 75 | 25 | encoder method 6/3/1 by profile |
| AVIF | 90 | 20 | encoder speed 4/6/8 by profile |

If even the floor is over the limit, the CLI raises an error; the GUI keeps the floor-quality file.

## GUI

- **Single module**, in order: configuration constants and speed profiles, FFmpeg helpers, layout and drawing, time selection, output builders, `RoundedButton`, then `ThumbnailMakerApp`.
- **Threading**: `Generate Thumbnails` starts one background thread. It walks the folders one at a time and runs a `ThreadPoolExecutor` of per-video jobs inside each folder, then builds `centerlongest` and `screen.png` for the folder.
- **UI updates** go through a `Queue` drained on the Tk thread every 60 ms. Message kinds are log, status, progress, file status, ETA, running state and `call` (run a function on the UI thread).
- **Run-time settings** (Footer toggle, Animation format) are copied into module globals when a run starts and the controls are locked while it runs. The last applied logo source and browse folder are remembered in `%APPDATA%/Pumpkin's Thumb It/settings.json`; logo size is session-only.
- **Stop**: a flag plus a shared `threading.Event` checked between animation frames; pending jobs are cancelled and unfinished files are marked Stopped.
- **Logo** loads in a background thread at startup; processing waits up to 20 s for it.

## CLI

`main` (`cli.py`) dispatches `doctor` or parses arguments, then `collect` → `group_inputs` → `preview` (dry run) or `process`.

- `process` builds a `Runner` and a `Renderer`, probes each folder's videos, then runs `one_video` jobs in a thread pool (`--jobs`), then makes the folder's `centerlongest` and `screen.png`.
- `Runner` (`media.py`) wraps every FFmpeg/FFprobe call with a timeout and a cancellation event; `probe` returns a `Video` dataclass.
- `Renderer` (`render.py`) draws sheets and encodes. `Renderer.save` writes to a temp file in the destination folder, fsyncs it, sets umask permissions and `os.replace`s it, so a failed run never leaves a partial output.
- Existing outputs are skipped if they open and decode cleanly (`valid_existing`); `--overwrite` forces a rebuild.
- Ctrl+C and SIGTERM stop running FFmpeg processes and cancel pending jobs.

## Keeping the two in sync

Layout constants (slot geometry, colours, corner radii, header text, animation buckets, size cap) are duplicated by hand. Known differences: the GUI uses Trebuchet and the CLI DejaVu; the GUI grabs animation frames one FFmpeg call each, the CLI decodes a clip in one call; the CLI sorts case-insensitively; the GUI's edge guard is fixed at 0.75 s while the CLI shrinks it for short videos.
