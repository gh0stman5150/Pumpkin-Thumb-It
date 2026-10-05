# Installation

## Windows GUI

**Requirements**: Windows, Python 3.9+, FFmpeg and FFprobe.

```bash
git clone https://github.com/PumpkinPounder/Pumpkin-Thumb-It.git
cd Pumpkin-Thumb-It
pip install opencv-python pillow numpy requests tkinterdnd2 psutil
```

`psutil` is optional (CPU limiting). **AVIF output** additionally needs Pillow 11.3 or newer with AVIF support; the app checks this when you pick AVIF and tells you if it is missing.

**FFmpeg**: the script looks for `C:\ffmpeg\bin\ffmpeg.exe` and `ffprobe.exe` first, then `PATH`. Either install FFmpeg to `C:\ffmpeg\bin`, add it to `PATH`, or edit `FFMPEG` / `FFPROBE` near the top of the script.

**Run**:

```bash
python "Pumpkin’s Thumb It 5.2.py"
```

## Linux CLI

**Requirements**: Python 3.10+, FFmpeg with FFprobe, Pillow with animated WebP support, and a TrueType font (DejaVu Sans Bold by default).

```bash
sudo apt update
sudo apt install -y ffmpeg fonts-dejavu-core pipx
pipx ensurepath
cd Pumpkin-Thumb-It/linux
pipx install .
thumb-it doctor
```

Open a new terminal after `pipx ensurepath`. Until then use `~/.local/bin/thumb-it`.

A virtual environment works too:

```bash
sudo apt install -y python3-venv ffmpeg fonts-dejavu-core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
thumb-it doctor
```

`doctor` should report FFmpeg, FFprobe, animated WebP encoding and a font. It also reports whether animated AVIF is available; this is optional.

Update with `pipx install --force .` from `linux/`; uninstall with `pipx uninstall pumpkins-thumb-it`.

## Developer setup

Run from `linux/`:

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

The end-to-end tests need `ffmpeg` and `ffprobe` on `PATH` and are skipped otherwise. See [testing.md](testing.md).

## Verify

- GUI: the window opens and logs the FFmpeg path. Add a video and press **Generate Thumbnails**; files appear in the video's `scr` folder.
- CLI: `thumb-it doctor` prints `Dependency checks passed.`; `thumb-it "/path/to/video.mp4"` writes `scr/` next to the video.
