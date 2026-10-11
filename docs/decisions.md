# Technical Decisions

Decisions below are inferred from the code and git history. Where the repo does not record a reason, that is stated.

## Two implementations instead of one shared library

The GUI is a single script with OpenCV, NumPy and Tkinter; the Linux CLI is a separate Pillow-and-FFmpeg package. This lets the CLI run over SSH and in cron with one Python dependency, at the cost of duplicated layout constants that must be edited in both places.

## v5 removed

The older orange-theme script was removed from the repository (it is in git history). It was no longer maintained and still rewrote its own source file when saving logo settings (see below), so keeping it risked users running the less safe version.

## Logo is blank by default and remembered in a settings file

v5 saved logo changes by rewriting its own source file with regular expressions: non-atomic, fails on read-only or synced folders, and leaves the script different from git. 5.1 removed this and made logo settings session-only. 5.2 starts with a blank logo (the old default was a third-party image URL) and remembers only the last logo source and the last browsed folder, in a small JSON file under `%APPDATA%` written atomically; unknown keys and wrongly typed values are ignored. Logo size stays per session. The CLI takes the logo on the command line each run.

## CLI defaults to no logo

So normal runs work offline and never fetch a remote image unless `--logo` is given. Remote logos have a 15 s timeout, a 20 MiB cap, and refuse redirects to non-HTTP(S) schemes; local logos have the same size cap. Errors show the host, not the full URL, so credentials are not logged.

## Atomic writes and validated skipping (CLI)

Outputs are encoded to a temp file, fsynced and `os.replace`d. A failure keeps the previous output, and a crash cannot leave a truncated image that later counts as "done". Skipping checks that the existing file decodes, not that it matches current settings, so `--overwrite` is the documented way to rebuild after changing inputs or options.

## Highest quality under the size cap

The old loop reduced quality in steps of 10 until a file fit, so a file just over the limit could drop far below it. Both implementations now search for the highest quality that fits. WebP is searched between the profile quality (85/75/70) and 25; AVIF between 90 and 20. In a synthetic test, WebP method 6 was about 18% smaller than method 3 at the same quality, so the speed profile now selects the method.

## WebP by default, AVIF opt-in

AVIF can look better at the same size, but the repo does not show whether upload destinations keep animated AVIF intact, and older viewers may not play it. WebP stays the default; AVIF is a GUI dropdown and `--format avif`. Both check that Pillow can actually write animated AVIF and fail loudly if not.

## Proxy-safe mode

`PROXY_SAFE_MODE = True` was added in v4.2 with no explanation in the repo. Today it sizes the longest-video clip at 960×540 (instead of 1280×720); its WebP quality cap of 75 was raised to 100 so the profile quality applies. The likely intent is keeping files small and cheap for an upload or image-host pipeline, but that is an inference. It is a hardcoded flag with no UI control and does not apply to AVIF.

## Reproducible frame choice

Still-frame times are seeded from a SHA-256 of the video path. The GUI previously used Python's `hash()`, which is salted per process, so a rebuilt sheet could show different stills than an existing animated sheet.

## 146 px header

The GUI header is 146 px with no logo; the CLI was 156 px. The CLI now matches the GUI, so default CLI sheets are 960 px tall instead of 970.

## Footer is an option, off by default

The orange footer bar was removed from outputs, but its code is kept behind a GUI toggle with custom text. Enabling it adds 34 px to the sheet height. The CLI has no footer.

## Tests are excluded from the installed package

An earlier commit removed tests to keep the Linux folder user-facing. Tests were restored under `linux/tests/`, outside the installed `thumb_it` package, so users still install only the CLI.

## Known trade-offs

- Per-frame FFmpeg process spawning is used in the GUI for animations. A single FFmpeg call per clip is faster, and the CLI already does this; the GUI still spawns about 360 processes per animated sheet.
- `minimize_size` in Pillow's WebP encoder gave no size benefit in testing and was slower, so it is not used.
