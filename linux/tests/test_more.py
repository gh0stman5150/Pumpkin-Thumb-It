"""Tests that need no FFmpeg: process runner, probe, collect, dry run, doctor, quality search."""
import contextlib
import io
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from thumb_it import cli, media, render
from thumb_it.media import Cancelled, MediaError, Runner


def touch(path, data=b""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class RunnerTests(unittest.TestCase):
    def runner(self, timeout=30):
        return Runner(sys.executable, sys.executable, timeout)

    def test_timeout_raises_media_error(self):
        with self.assertRaises(MediaError) as raised:
            self.runner(timeout=0.5).run([sys.executable, "-c", "import time; time.sleep(30)"])
        self.assertIn("timed out", str(raised.exception))

    def test_cancel_raises_cancelled_and_stops_process(self):
        runner = self.runner()
        timer = threading.Timer(0.4, runner.stopped.set)
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaises(Cancelled):
            runner.run([sys.executable, "-c", "import time; time.sleep(30)"])

    def test_nonzero_exit_includes_stderr(self):
        with self.assertRaises(MediaError) as raised:
            self.runner().run([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])
        self.assertIn("boom", str(raised.exception))

    def test_success_returns_stdout(self):
        self.assertEqual(self.runner().run([sys.executable, "-c", "print('hi', end='')"]), b"hi")

    def test_missing_tool(self):
        with self.assertRaises(MediaError):
            media.resolve_tool("definitely-not-a-real-tool-xyz")


class FakeRunner:
    ffprobe = "ffprobe"

    def __init__(self, payload):
        self.payload = payload

    def run(self, command):
        return self.payload


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = touch(Path(self.tmp.name) / "v.mp4", b"x" * 10)

    def probe(self, json_text):
        return media.probe(FakeRunner(json_text.encode()), self.path)

    def test_video_and_audio_fields(self):
        video = self.probe('{"streams":[{"index":0,"codec_type":"video","codec_name":"h264","width":1920,'
                           '"height":1080,"avg_frame_rate":"30000/1001","bit_rate":"4000000"},'
                           '{"index":1,"codec_type":"audio","codec_name":"aac","channels":2,"bit_rate":"128000"}],'
                           '"format":{"duration":"60.5"}}')
        self.assertEqual((video.width, video.height, video.duration), (1920, 1080, 60.5))
        self.assertAlmostEqual(video.fps, 29.97, places=2)
        self.assertEqual((video.vcodec, video.acodec, video.channels, video.size), ("h264", "aac", 2, 10))
        self.assertEqual(video.vbitrate, 4000)

    def test_stream_duration_wins_over_format(self):
        video = self.probe('{"streams":[{"index":0,"codec_type":"video","width":4,"height":4,"duration":"5"}],'
                           '"format":{"duration":"9"}}')
        self.assertEqual(video.duration, 5.0)

    def test_zero_over_zero_frame_rate(self):
        video = self.probe('{"streams":[{"index":0,"codec_type":"video","width":4,"height":4,'
                           '"avg_frame_rate":"0/0"}],"format":{"duration":"5"}}')
        self.assertEqual(video.fps, 0)

    def test_audio_missing_is_none(self):
        video = self.probe('{"streams":[{"index":0,"codec_type":"video","width":4,"height":4}],'
                           '"format":{"duration":"5"}}')
        self.assertEqual(video.acodec, "none")

    def test_attached_picture_only_is_not_video(self):
        with self.assertRaises(MediaError):
            self.probe('{"streams":[{"index":0,"codec_type":"video","width":4,"height":4,'
                       '"disposition":{"attached_pic":1}}],"format":{"duration":"5"}}')

    def test_no_duration_or_bad_json_rejected(self):
        with self.assertRaises(MediaError):
            self.probe('{"streams":[{"index":0,"codec_type":"video","width":4,"height":4}],"format":{}}')
        with self.assertRaises(MediaError):
            self.probe("not json")


class CollectEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def test_duplicate_inputs_deduplicated(self):
        video = touch(self.root / "a.mp4")
        files, _ = cli.collect([str(video), str(video), str(self.root)], recursive=False)
        self.assertEqual(files, [video])

    def test_uppercase_scr_directory_skipped(self):
        touch(self.root / "SCR" / "old.mp4")
        keep = touch(self.root / "keep.mp4")
        files, _ = cli.collect([str(self.root)], recursive=True)
        self.assertEqual(files, [keep])

    def test_directory_symlink_not_followed(self):
        target = self.root / "real"
        touch(target / "inside.mp4")
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("cannot create symlinks here")
        files, _ = cli.collect([str(self.root)], recursive=True)
        self.assertEqual(files, [target / "inside.mp4"])

    def test_error_messages(self):
        txt = touch(self.root / "x.txt")
        _, errors = cli.collect([str(self.root / "nope"), str(txt)], recursive=False)
        self.assertTrue(any("does not exist" in e for e in errors))
        self.assertTrue(any("Unsupported video extension" in e for e in errors))


class DryRunTests(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch("shutil.which", return_value=None):
            code = cli.main([*args, "--dry-run"])
        return code, out.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.video = touch(Path(self.tmp.name) / "v.mp4")

    def test_default_plan(self):
        code, text = self.run_cli(str(self.video))
        self.assertEqual(code, 0)
        for name in ("sheet_v.png", "center1.webp", "centerlongest_", "screen.png"):
            self.assertIn(name, text)

    def test_sheets_only_omits_animations(self):
        _, text = self.run_cli(str(self.video), "--sheets-only")
        self.assertIn("sheet_v.png", text)
        self.assertNotIn("center", text)

    def test_avif_extension(self):
        _, text = self.run_cli(str(self.video), "--format", "avif")
        self.assertIn("center1.avif", text)
        self.assertNotIn(".webp", text)

    def test_zero_animated_sheets(self):
        _, text = self.run_cli(str(self.video), "--animated-sheets", "0")
        self.assertNotIn("center1", text)
        self.assertIn("centerlongest_", text)

    def test_missing_input_returns_1(self):
        code, _ = self.run_cli(str(self.video), str(Path(self.tmp.name) / "missing"))
        self.assertEqual(code, 1)


class DoctorTests(unittest.TestCase):
    def test_missing_ffmpeg_fails(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["doctor", "--ffmpeg", "definitely-not-a-real-tool-xyz"])
        self.assertEqual(code, 1)
        self.assertIn("Cannot find", err.getvalue())


class FakeFrame:
    """Stands in for an image: encoded size is quality * 100 bytes, so the search is deterministic."""

    def __init__(self):
        self.calls = []

    def save(self, buffer, **kwargs):
        self.calls.append(kwargs)
        buffer.write(b"x" * (kwargs["quality"] * 100))


class QualitySearchTests(unittest.TestCase):
    def renderer(self, limit, fmt="webp"):
        renderer = render.Renderer.__new__(render.Renderer)
        renderer.settings = render.Settings(max_webp_bytes=limit, fps=12, format=fmt)
        renderer.runner = type("R", (), {"check": lambda self: None})()
        return renderer

    def search(self, limit, start=75, floor=25, fmt="webp"):
        frame = FakeFrame()
        data = self.renderer(limit, fmt).fit_animation([frame], start, 3, "t", floor)
        return len(data) // 100, frame

    def test_fits_first_try(self):
        quality, frame = self.search(10000)
        self.assertEqual((quality, len(frame.calls)), (75, 1))

    def test_picks_highest_fitting_quality(self):
        quality, _ = self.search(6234)
        self.assertEqual(quality, 62)

    def test_exactly_at_floor(self):
        self.assertEqual(self.search(2500)[0], 25)

    def test_below_floor_raises(self):
        with self.assertRaises(MediaError):
            self.search(2499)

    def test_start_at_floor_and_too_big_raises(self):
        with self.assertRaises(MediaError):
            self.search(100, start=25)

    def test_avif_passes_speed_and_format(self):
        _, frame = self.search(9000, start=90, floor=20, fmt="avif")
        self.assertTrue(all(call["format"] == "AVIF" and call["speed"] == 3 for call in frame.calls))


class SaveRobustnessTests(unittest.TestCase):
    def renderer(self, check):
        renderer = render.Renderer.__new__(render.Renderer)
        renderer.settings = render.Settings()
        renderer.runner = type("R", (), {"check": lambda self: check()})()
        return renderer

    def test_cancel_after_temp_write_leaves_nothing(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.png"

            def check():
                # Cancel only once the temporary file exists: after the write, before the replace.
                if any(p.suffix == ".tmp" for p in Path(tmp).iterdir()):
                    raise Cancelled("stop")

            with self.assertRaises(Cancelled):
                self.renderer(check).save(target, Image.new("RGB", (8, 8)))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_mode_follows_umask(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(render, "UMASK", 0o077):
            target = Path(tmp) / "out.png"
            self.renderer(lambda: None).save(target, Image.new("RGB", (8, 8)))
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)


class FakeResponse:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size=-1):
        end = len(self.data) if size < 0 else self.offset + size
        chunk = self.data[self.offset:end]
        self.offset += len(chunk)
        return chunk


class LogoLoadingTests(unittest.TestCase):
    def png(self, directory, size):
        from PIL import Image
        path = Path(directory) / "logo.png"
        Image.new("RGB", size, "red").save(path)
        return path

    def test_local_logo_resized_to_fit_and_rgba(self):
        with tempfile.TemporaryDirectory() as tmp:
            logo = render.load_logo(str(self.png(tmp, (800, 400))), 100, 100)
        self.assertEqual(logo.mode, "RGBA")
        self.assertLessEqual(logo.width, 100)
        self.assertLessEqual(logo.height, 100)
        self.assertEqual(logo.width, 100)

    def test_not_an_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = touch(Path(tmp) / "x.png", b"not an image")
            with self.assertRaises(MediaError):
                render.load_logo(str(path), 100, 100)

    def test_too_many_pixels(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(render, "LOGO_MAX_PIXELS", 10):
            with self.assertRaises(MediaError) as raised:
                render.load_logo(str(self.png(tmp, (8, 8))), 100, 100)
        self.assertIn("too many pixels", str(raised.exception))

    def test_remote_oversize_rejected(self):
        with mock.patch.object(render, "LOGO_MAX_BYTES", 5), \
                mock.patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(b"x" * 100)):
            with self.assertRaises(MediaError) as raised:
                render.load_logo("https://example.com/logo.png", 100, 100)
        self.assertIn("exceeds", str(raised.exception))

    def test_remote_error_is_sanitised_and_mentions_host(self):
        with mock.patch("urllib.request.OpenerDirector.open", side_effect=urllib.error.URLError("boom")):
            with self.assertRaises(MediaError) as raised:
                render.load_logo("http://user:secret@logos.example/a.png?token=abc", 100, 100)
        message = str(raised.exception)
        self.assertIn("Cannot load logo 'logos.example'", message)
        self.assertNotIn("secret", message)
        self.assertNotIn("token", message)

    def test_redirect_to_non_http_refused(self):
        handler = render._WebRedirects()
        with self.assertRaises(urllib.error.URLError):
            handler.redirect_request(mock.Mock(), None, 302, "Found", {}, "ftp://example.com/x.png")

    def test_valid_existing_decodes_first_and_last_frame_only(self):
        from PIL import Image, WebPImagePlugin
        frames = [Image.new("RGB", (32, 32), c) for c in ("red", "green", "blue", "white")]
        seen = []
        original = WebPImagePlugin.WebPImageFile.seek

        def recording_seek(self, frame):
            seen.append(frame)
            return original(self, frame)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.webp"
            frames[0].save(path, format="WEBP", save_all=True, append_images=frames[1:], duration=50, loop=0)
            with mock.patch.object(WebPImagePlugin.WebPImageFile, "seek", recording_seek):
                self.assertTrue(render.valid_existing(path))
        self.assertEqual(sorted(set(seen)), [0, 3])

    def test_valid_existing_rejects_truncated_animation(self):
        from PIL import Image
        frames = [Image.new("RGB", (32, 32), c) for c in ("red", "green", "blue")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.webp"
            frames[0].save(path, format="WEBP", save_all=True, append_images=frames[1:], duration=50, loop=0)
            path.write_bytes(path.read_bytes()[:-20])
            with self.assertRaises(MediaError):
                render.valid_existing(path)

    def test_valid_existing_suffix_is_case_insensitive(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.WEBP"
            Image.new("RGB", (8, 8)).save(path, format="WEBP")
            self.assertTrue(render.valid_existing(path))


class FakeDecodeRunner:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def decode(self, video, args, start=0):
        self.calls.append((args, start))
        return self.raw

    def check(self):
        pass


class ClipTests(unittest.TestCase):
    SIZE = (4, 3)
    STRIDE = 4 * 3 * 3

    def renderer(self, raw):
        renderer = render.Renderer.__new__(render.Renderer)
        renderer.runner = FakeDecodeRunner(raw)
        return renderer

    def raw(self, n):
        return b"".join(bytes([i]) * self.STRIDE for i in range(n))

    def clip(self, raw, count):
        video = mock.Mock(path=Path("v.mp4"), stream=0)
        renderer = self.renderer(raw)
        return renderer.clip(video, 1.0, 2.0, count, self.SIZE), renderer.runner

    def test_exact_count(self):
        frames, runner = self.clip(self.raw(4), 4)
        self.assertEqual([f.getpixel((0, 0))[0] for f in frames], [0, 1, 2, 3])
        args, start = runner.calls[0]
        self.assertEqual(start, 1.0)
        self.assertIn("fps=2.00000000:start_time=0", " ".join(args))

    def test_short_output_pads_with_last_frame(self):
        frames, _ = self.clip(self.raw(2), 5)
        self.assertEqual([f.getpixel((0, 0))[0] for f in frames], [0, 1, 1, 1, 1])

    def test_extra_frames_truncated(self):
        frames, _ = self.clip(self.raw(6), 3)
        self.assertEqual(len(frames), 3)

    def test_partial_trailing_frame_rejected(self):
        with self.assertRaises(MediaError):
            self.clip(self.raw(2) + b"x", 2)

    def test_empty_output_rejected(self):
        with self.assertRaises(MediaError):
            self.clip(b"", 2)


class PasteSlotGoldenTests(unittest.TestCase):
    """The cached mask/shadow must give pixel-identical results to the original per-call code."""

    def reference(self, sheet, thumb, slot):
        from PIL import Image, ImageDraw, ImageFilter
        x, y, width, height, big = slot
        thumb = thumb.resize((width, height), Image.Resampling.LANCZOS).convert("RGBA")
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=28 if big else 18, fill=255)
        thumb.putalpha(mask)
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        shadow.putalpha(mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
        layer = Image.new("RGBA", sheet.size)
        layer.paste(shadow, (x, y + 4), shadow)
        sheet.alpha_composite(layer)
        sheet.paste(thumb, (x, y), thumb)

    def check(self, slot, thumb_size):
        from PIL import Image
        thumb = Image.effect_noise(thumb_size, 60).convert("RGB")
        a = Image.new("RGBA", (180, 140), (35, 35, 35, 255))
        b = a.copy()
        render.paste_slot(a, thumb, slot)
        self.reference(b, thumb, slot)
        self.assertEqual(a.tobytes(), b.tobytes())

    def test_small_slot(self):
        self.check((10, 10, 40, 30, False), (40, 30))

    def test_big_slot_with_resize(self):
        self.check((20, 15, 80, 60, True), (50, 20))

    def test_slot_touching_the_edge(self):
        self.check((140, 110, 40, 30, False), (40, 30))


if __name__ == "__main__":
    unittest.main()
