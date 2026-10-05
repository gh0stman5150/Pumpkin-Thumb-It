# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Pumpkin's Thumb It generates video thumbnail sheets (PNG), animated WebP sheets, a "longest video" preview and a `screen.png` per folder. There are two independent implementations in one repo; they share no code and must be kept visually consistent by hand:

- **Windows GUI** — two standalone, single-file Tkinter scripts at the repo root (~2500 lines each): `Pumpkin’s Thumb It 5.1.py` (current, dark/lime theme) and `Pumpkin’s Thumb It v5.py` (legacy orange theme, kept for users). Filenames contain a Unicode right quote (`’`), so quote paths in shell commands. Dependencies: OpenCV, NumPy, requests, Pillow, tkinterdnd2; Python 3.9+. No build, package or test setup; run with `python "Pumpkin’s Thumb It 5.1.py"`. FFmpeg paths are hardcoded near the top (`FFMPEG`/`FFPROBE` = `C:\ffmpeg\bin\...`, `FONT_PATH` = Trebuchet) and all layout/behaviour constants (sheet geometry, speed profiles, WebP size caps, proxy-safe mode) are module-level globals at the top of the file.
- **Linux CLI** — `linux/` is a self-contained pip-installable package (`pumpkins-thumb-it`, command `thumb-it`, Python 3.10+, only Pillow as a Python dependency plus system `ffmpeg`/`ffprobe` and a TTF font). No Tkinter/OpenCV/NumPy. It is a port of the 5.1 layout, not an import of the GUI script.

`ffmpeg.exe`, `ffplay.exe` and `ffprobe.exe` in the repo root are untracked local binaries; do not commit them.

## Linux CLI (`linux/`)

Run commands from `linux/`:

```bash
python -m pip install .            # or: pipx install .
thumb-it doctor                    # verifies ffmpeg, ffprobe, animated WebP support, font
thumb-it PATH --dry-run            # lists outputs without decoding or needing ffmpeg/Pillow
python -m build                    # build sdist/wheel (CI does this)
```

There is no test suite or linter in the repo (test files are intentionally excluded from the package); CI (`.github/workflows/linux-cli.yml`) builds the wheel, installs it, and runs `thumb-it --help/--version/doctor` outside the source dir on Ubuntu 22.04/py3.10, Ubuntu 24.04/py3.12 & 3.14, and Debian 12/py3.11, plus a pipx install check and Pillow 10.4.0 minimum-version check. CI only triggers on changes to `linux/**`, `README.md` or the workflow file.

Module layout (`linux/thumb_it/`):
- `cli.py` — argparse (`make_parser`, bounded-number validators), input collection/grouping by folder, `doctor` subcommand, `--dry-run` preview, and `process` (thread pool of per-video jobs, then per-folder previews; Ctrl+C/SIGTERM cancel running FFmpeg processes). `doctor` is detected as the first argv token, so a directory named `doctor` must be passed as `./doctor`.
- `media.py` — `Runner` (FFmpeg/FFprobe subprocess wrapper with timeout and cancellation → `MediaError`/`Cancelled`), `probe()` returning a `Video` dataclass.
- `render.py` — `Settings` dataclass, 5.1 layout constants (237×124 small / 484×258 big slots, 1492px sheet width, 16 small + 5 big slots), font/WebP checks, logo loading (local or HTTP(S) with 15s timeout / 20 MiB cap), and `Renderer` which builds sheets/animations and encodes WebP with quality reduction to fit `--max-webp-mib`.

Behaviours worth knowing: outputs go to a `scr/` subfolder next to the videos; files are written to temp files then atomically replaced; existing readable outputs are skipped by default (`valid_existing`), `--overwrite` forces rebuild; `--recursive` omits `scr` dirs and does not follow directory symlinks; the default is no logo (offline-safe); same-stem videos in one folder are rejected. `linux/README.md` holds the full CLI reference — update it (and the version in `pyproject.toml` / `thumb_it/__init__.py`) when changing options or defaults.

## Keeping the implementations in sync

Layout constants (sheet geometry, colours, header/banner, rounded corners, no promotional footer, 5-animated-sheets-per-folder, 6s/12fps animations, 5 MiB WebP cap) are duplicated between the GUI 5.1 script and `linux/thumb_it/render.py`. A visual/layout change usually needs to be made in both. The GUI additionally keeps legacy footer code (`draw_footer`, `add_footer_to_image`), but `FOOTER_HEIGHT = 0` / empty `FOOTER_TEXT` so outputs are footer-free.
