# Project Structure

```text
Pumpkin-Thumb-It/
├── Pumpkin’s Thumb It 5.2.py      # current Windows GUI (dark/lime theme)
├── README.md
├── LICENSE
├── CLAUDE.md                       # guidance for Claude Code
├── docs/                           # this documentation
├── linux/
│   ├── README.md                   # CLI install and full reference
│   ├── pyproject.toml              # package metadata (pumpkins-thumb-it, thumb-it)
│   ├── thumb_it/
│   │   ├── __init__.py             # __version__
│   │   ├── __main__.py             # python -m thumb_it
│   │   ├── cli.py                  # arguments, input collection, doctor, job scheduling
│   │   ├── media.py                # FFmpeg/FFprobe runner, probe, Video dataclass
│   │   └── render.py               # layout, sheet drawing, encoding, logo loading
│   ├── LICENSE                     # copy of the root license so the wheel and sdist include it
│   └── tests/
│       ├── test_cli.py             # CLI unit and end-to-end tests
│       ├── test_more.py            # FFmpeg-free tests: runner, probe, dry run, rendering internals
│       └── test_gui_pure.py        # tests for the GUI script's pure helpers (not installed with the package)
└── .github/workflows/linux-cli.yml # CI for the Linux CLI
```

Untracked local files such as `ffmpeg.exe`, `ffplay.exe` and `ffprobe.exe` may sit in the repo root. `*.exe` is ignored.

## Responsibilities

| Path | Responsibility |
| --- | --- |
| `Pumpkin’s Thumb It 5.2.py` | Everything for the GUI: constants, FFmpeg helpers, rendering, UI. Filenames contain a Unicode right quote (`’`), so quote them in shell commands. |
| `linux/thumb_it/cli.py` | Parsing, validation, `collect` / `group_inputs`, `doctor`, the thread pool and exit codes. No image or FFmpeg work. |
| `linux/thumb_it/media.py` | Process execution only: timeouts, cancellation, ffprobe parsing. |
| `linux/thumb_it/render.py` | All drawing and encoding, atomic writes, output validation. Imports `media`, never `cli`. |
| `linux/tests/` | Unit tests plus FFmpeg end-to-end tests; excluded from the wheel by `[tool.setuptools.packages.find]`. |

## What should not go where

- GUI code and CLI code are separate. Do not import the GUI script from the CLI.
- `cli.py` should not touch Pillow directly; `process` imports `render` lazily so `--dry-run` works without Pillow or FFmpeg.
- Version strings live in `linux/pyproject.toml`, `linux/thumb_it/__init__.py` and `APP_VERSION` in the GUI script. Update them together.
