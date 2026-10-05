# CLI Reference

Summary of the `thumb-it` command. The full reference with examples is in [linux/README.md](../linux/README.md).

```text
thumb-it [options] PATH [PATH ...]
thumb-it doctor [--ffmpeg PATH] [--ffprobe PATH] [--font PATH] [--timeout SECONDS]
thumb-it --version | --help
python -m thumb_it ...
```

Paths are video files or folders. Supported extensions (case-insensitive): `.mp4 .m4v .mkv .mov .avi .wmv`. A folder named `doctor` must be passed as `./doctor`.

## Options

| Option | Default | Notes |
| --- | --- | --- |
| `-r`, `--recursive` | off | Include subfolders; skips `scr/` and directory symlinks |
| `--format webp\|avif` | `webp` | Animated output format; AVIF needs Pillow 11.3+ |
| `--speed normal\|fast\|fastest` | `fast` | Animation encoder effort (WebP method 6/3/1, AVIF speed 4/6/8) |
| `--overwrite` / `--skip-existing` | skip | Mutually exclusive |
| `--logo PATH_OR_URL` / `--no-logo` | no logo | Mutually exclusive; remote logos: 15 s timeout, 20 MiB cap |
| `--logo-width`, `--logo-height` | 420, 120 | 1–600 pixels |
| `--sheets-only` | off | PNG sheets only |
| `--animated-sheets COUNT` | 5 | 0–5 videos per folder get `centerN` |
| `--seconds`, `--fps` | 6, 12 | `seconds × fps` must be ≤ 120 |
| `--max-webp-mib MIB` | 5 | Size cap for each animated image (WebP or AVIF) |
| `--jobs COUNT` | up to 2 | 1–32 videos at once |
| `--dry-run` | off | List intended outputs; needs no FFmpeg or Pillow |
| `--quiet` | off | Errors and the final summary still print |
| `--ffmpeg`, `--ffprobe`, `--font`, `--timeout` | PATH, discovered, 120 s | Also accepted by `doctor` |

## Output names

`scr/sheet_<stem>.png`, `scr/center<N>.<ext>` (N = 1–5), `scr/centerlongest_<folder>.<ext>`, `scr/screen.png`, where `<ext>` is `webp` or `avif`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | All work succeeded or valid outputs were skipped |
| 1 | An input, dependency or processing failure (other videos may have finished); also no supported videos found |
| 2 | Invalid arguments or colliding output names |
| 130 | Interrupted by Ctrl+C or SIGTERM |

Errors go to standard error; progress and the summary go to standard output.

## Python modules

Not a documented public API, but `thumb_it.render.Settings` (frozen dataclass: `speed`, `seconds`, `fps`, `max_webp_bytes`, `logo`, `logo_width`, `logo_height`, `font`, `format`) and `Renderer(runner, settings)` are what the CLI uses. `Renderer.sheet`, `animated_sheet`, `center` and `frame` build images; `Renderer.save` writes them atomically.
