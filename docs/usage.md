# Usage

## GUI workflow

1. Run `python "Pumpkin’s Thumb It 5.2.py"`.
2. Add videos with **Add Videos**, **Add Video Folder** or drag and drop. Each of these replaces the current list.
3. Choose **Speed** (Normal, Fast, Fastest) and **Animation** (WebP or AVIF).
4. Optional, under **Sheet Settings**:
   - **Logo**: URL or local file, maximum width and height. **Preview** shows a mock header; **Apply Logo** applies it. The field starts blank; the last applied logo and the last folder you browsed are remembered for the next launch (apply a blank logo to forget it). Width and height are for this session only.
   - **Skip Existing**: ON skips outputs already in `scr/`; OFF rebuilds them.
   - **Footer**: ON adds your text in an orange bar under every sheet and animation (34 px extra height).
5. Press **Generate Thumbnails**. The queue shows each file's status; the footer bar shows progress and ETA.
6. **Stop After Current Task** stops between animation frames; unfinished files are marked Stopped.

Logo, Footer and Animation controls are locked while a run is in progress.

## CLI workflow

```bash
thumb-it "/media/videos/My Video.mp4"           # one video; outputs in /media/videos/scr/
thumb-it "/media/videos" --recursive            # every folder gets its own scr/
thumb-it "/media/videos" --recursive --dry-run  # list outputs, write nothing
thumb-it "/media/videos" --format avif          # animated .avif instead of .webp
thumb-it "/media/videos" --sheets-only --jobs 1 # PNG sheets only, lowest memory
thumb-it "/media/videos" --overwrite            # rebuild after changing options or files
```

Always quote paths with spaces. See [api.md](api.md) for the option table and exit codes.

## Outputs

Per folder, in `scr/`: `sheet_<video>.png` for every video; `center1`–`center5` for the first five videos (sorted by name); `centerlongest_<folder>` and `screen.png` for the longest video. The animated files are `.webp` or, when AVIF is selected, `.avif`.

## Things to know

- **Skip Existing / default CLI behaviour** does not notice changed settings. After changing the logo, format, footer or the set of videos, rebuild (GUI: Skip Existing OFF; CLI: `--overwrite`). Changing the format changes the file extension, so the other format's files are left behind.
- **Footer ON with Skip Existing ON** adds the footer to existing images that lack it; turning it OFF does not remove a footer from files that already have one.
- **Two videos with the same name stem** in one folder (`clip.mp4`, `clip.mkv`) collide on `sheet_clip.png`. The CLI rejects this up front; the GUI does not.
- **Size cap**: each animation is held to 5 MiB by default (`MAX_WEBP_BYTES`, `--max-webp-mib`). If the floor quality still does not fit, the CLI errors and the GUI keeps the floor-quality file. Shorten `--seconds` / `--fps` to shrink it.
- **Memory**: an animated sheet holds every frame in memory (about 420 MB for 72 frames). Use `--jobs 1` or a shorter clip on small machines.
- **AVIF** needs Pillow 11.3+. If it is missing, the GUI shows a warning and the CLI exits with an error; use WebP.

## Common problems

| Symptom | Fix |
| --- | --- |
| FFmpeg not found | GUI: install to `C:\ffmpeg\bin`, add to `PATH`, or edit `FFMPEG`/`FFPROBE`. CLI: install `ffmpeg` or pass `--ffmpeg` / `--ffprobe`. |
| `thumb-it: command not found` | Open a new terminal after `pipx ensurepath`, or run `~/.local/bin/thumb-it`. |
| Font missing (CLI) | `sudo apt install fonts-dejavu-core` or pass `--font /path/to/font.ttf`. |
| Logo does not load | Check the path or URL and the size fields. The GUI silently skips a bad logo; the CLI reports an error. |
| Existing output unreadable (CLI) | Run with `--overwrite`. |
| Sheets look different between GUI and CLI | Fonts differ (Trebuchet vs DejaVu), so text widths and truncation differ slightly. |
