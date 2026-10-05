# Testing

The CLI has a full `unittest` suite. The GUI has tests for its pure helpers only (quality search, seeds, atomic writes, clip assembly, paste output); its window and the full render path are checked with `python -m py_compile` and by running it.

## Run the tests

From `linux/`:

```bash
python -m unittest discover -s tests -v
```

Single test:

```bash
python -m unittest tests.test_cli.SaveTests.test_png_saved_with_umask_permissions_and_no_temp_left
```

No pytest or other test dependency is needed. The end-to-end classes need `ffmpeg` and `ffprobe` on `PATH` and are skipped without them (on Windows, put the folder containing `ffmpeg.exe` on `PATH`). The AVIF end-to-end test is also skipped if Pillow cannot write animated AVIF.

Environment variables:

| Variable | Effect |
| --- | --- |
| `REQUIRE_FFMPEG=1` | A missing `ffmpeg`/`ffprobe` fails a test instead of skipping the end-to-end tests (CI sets it) |
| `REQUIRE_GUI_TESTS=1` | Failing to load the GUI script fails a test instead of skipping `test_gui_pure.py` (CI sets it) |
| `THUMB_IT_REPO=<path>` | Repository root, for when the tests are run from a copy outside `linux/` (CI does this) |

The GUI script is loaded by path. Desktop packages that are not installed (`tkinter`, `cv2`, `tkinterdnd2`, `requests`, `numpy`) are replaced by stubs for the duration of the import, so the GUI helper tests run on Linux CI.

## What the tests cover (`linux/tests/`)

| Area | Examples |
| --- | --- |
| Argument validation | `bounded_number` ranges, NaN/inf rejection, `seconds × fps` limit exits 2 |
| Input collection | extension case, non-recursive vs recursive, `scr/` skipped, missing and unsupported inputs, same-stem collisions, folder tag sanitising |
| Layout | 21 slots, 5 big, sheet height 960 at the default header |
| Logo | oversized local file rejected, credentials not echoed in errors, non-HTTP(S) redirects refused |
| Saving | PNG written with umask permissions and no temp files left, unfittable WebP raises and cleans up, truncated file flagged by `valid_existing`, quality search fits under the limit |
| End to end | a generated `testsrc` clip produces the full pack in WebP and in AVIF, and a rerun skips existing files |
| Dry run | writes nothing and needs no FFmpeg; prints the right names for `--sheets-only`, `--format avif`, `--animated-sheets 0`; missing input returns 1 |
| Process runner and probe (`test_more.py`) | timeout, cancellation, non-zero exit text, canned ffprobe JSON including `0/0` frame rate, attached pictures and missing duration |
| Rendering internals (`test_more.py`) | `Renderer.clip` frame count, padding and rejection; `paste_slot` pixel-identical to the original uncached code; exact quality-search results with a deterministic fake encoder |
| Output safety (`test_more.py`) | cancel after the temp write leaves nothing, umask permissions, first/last-frame validation, case-insensitive suffixes, logo size/pixel/redirect/credential handling |
| `doctor` | a missing FFmpeg returns 1 and reports `Cannot find` |
| GUI helpers (`test_gui_pure.py`) | quality search, `_stable_seed` across processes, atomic write and umask, probe cache, failure logging, `_slot_clip_frames` fallbacks and padding, `_paste_thumb_in_slot` pixel-identical to the original code |

## Not covered

- The GUI window, event handling and the full render path.
- Timestamp selection in `Renderer.stills` and the bucket arithmetic in `Renderer.animated_sheet` without FFmpeg.
- Non-UTF-8 filenames, symlinked video files, and a real remote-logo download (the logo tests use mocks, not an HTTP server).

## Continuous integration

`.github/workflows/linux-cli.yml` runs on changes to `linux/**`, `docs/**`, `README.md` or the workflow. For each job it builds the wheel, installs it, runs `thumb-it --help`, `--version` and `doctor` outside the source directory, then the test suite. The tests run from a copy outside `linux/` so they import the installed wheel, and the job fails if ffmpeg or the GUI script is unavailable:

- Ubuntu 22.04 / Python 3.10 (also reruns `doctor` and the tests with Pillow 10.4.0, the minimum supported)
- Ubuntu 24.04 / Python 3.12 and 3.14
- Debian 12 / Python 3.11

The Ubuntu jobs also verify the README's `pipx install .` path. Built wheels are uploaded as artifacts. There is no coverage configuration.
