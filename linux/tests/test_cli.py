import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from thumb_it import cli, render
from thumb_it.media import MediaError


def touch(path, data=b""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class BoundedNumberTests(unittest.TestCase):
    def test_accepts_range_and_rejects_outside(self):
        parse = cli.bounded_number(1, 10, integer=True)
        self.assertEqual(parse("5"), 5)
        for bad in ("0", "11", "x", "1.5"):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse(bad)

    def test_rejects_non_finite(self):
        parse = cli.bounded_number(0, 10)
        for bad in ("nan", "inf", "-inf"):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse(bad)


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def test_extension_case_and_non_recursive(self):
        a = touch(self.root / "A.MP4")
        touch(self.root / "notes.txt")
        touch(self.root / "sub" / "b.mkv")
        files, errors = cli.collect([str(self.root)], recursive=False)
        self.assertEqual(files, [a])
        self.assertEqual(errors, [])

    def test_recursive_skips_scr(self):
        a = touch(self.root / "a.mp4")
        b = touch(self.root / "sub" / "b.mkv")
        touch(self.root / "scr" / "old.mp4")
        files, _ = cli.collect([str(self.root)], recursive=True)
        self.assertEqual(sorted(files), sorted([a, b]))

    def test_missing_and_unsupported_inputs_reported(self):
        txt = touch(self.root / "x.txt")
        files, errors = cli.collect([str(self.root / "missing"), str(txt)], recursive=False)
        self.assertEqual(files, [])
        self.assertEqual(len(errors), 2)

    def test_same_stem_collision(self):
        paths = [touch(self.root / "clip.mp4").resolve(), touch(self.root / "clip.mkv").resolve()]
        with self.assertRaises(ValueError):
            cli.group_inputs(paths)

    def test_folder_tag_sanitised_and_capped(self):
        self.assertEqual(cli.folder_tag(Path("/x/My Pack: 1")), "My_Pack__1")
        self.assertLessEqual(len(cli.folder_tag(Path("/x/" + "a" * 200))), 80)


class LayoutTests(unittest.TestCase):
    def test_default_sheet_width(self):
        slots, height = render.layout(146)
        self.assertEqual(len(slots), 21)
        self.assertEqual(sum(1 for s in slots if s[4]), 5)
        self.assertEqual(height, 960)


class MainTests(unittest.TestCase):
    def test_seconds_times_fps_limit_exits_2(self):
        with self.assertRaises(SystemExit) as raised:
            cli.main(["x.mp4", "--seconds", "30", "--fps", "60"])
        self.assertEqual(raised.exception.code, 2)

    def test_dry_run_needs_no_ffmpeg_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = touch(Path(tmp) / "v.mp4")
            self.assertEqual(cli.main([str(video), "--dry-run", "--quiet"]), 0)
            self.assertFalse((Path(tmp) / "scr").exists())

    def test_no_videos_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.main([tmp, "--quiet"]), 1)


class LogoTests(unittest.TestCase):
    def test_oversized_local_logo_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.png"
            with open(big, "wb") as handle:
                handle.truncate(render.LOGO_MAX_BYTES + 1)
            with self.assertRaises(MediaError):
                render.load_logo(str(big), 100, 100)

    def test_error_hides_url_credentials(self):
        with self.assertRaises(MediaError) as raised:
            render.load_logo("http://user:secret@127.0.0.1:9/logo.png", 100, 100)
        self.assertNotIn("secret", str(raised.exception))

    def test_redirect_to_non_http_refused(self):
        handler = render._WebRedirects()
        with self.assertRaises(Exception):
            handler.redirect_request(None, None, 302, "Found", {}, "ftp://example.com/x.png")


class SaveTests(unittest.TestCase):
    def make_renderer(self):
        renderer = render.Renderer.__new__(render.Renderer)
        renderer.settings = render.Settings(max_webp_bytes=1)
        renderer.runner = type("R", (), {"check": lambda self: None})()
        return renderer

    def test_png_saved_with_umask_permissions_and_no_temp_left(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "scr" / "out.png"
            self.make_renderer().save(target, Image.new("RGB", (8, 8)))
            self.assertEqual([p.name for p in target.parent.iterdir()], ["out.png"])
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o666 & ~render.UMASK)

    def test_unfittable_webp_raises_and_cleans_up(self):
        from PIL import Image
        frames = [Image.new("RGB", (64, 64), c) for c in ("red", "blue")]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.webp"
            with self.assertRaises(MediaError):
                self.make_renderer().save(target, frames, animated=True)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_quality_search_fits_limit_with_best_quality(self):
        import io
        import random
        from PIL import Image
        rng = random.Random(1)
        frames = [Image.frombytes("RGB", (96, 96), bytes(rng.randrange(256) for _ in range(96 * 96 * 3)))
                  for _ in range(3)]

        def size(quality):
            buffer = io.BytesIO()
            frames[0].save(buffer, format="WEBP", save_all=True, append_images=frames[1:],
                           duration=83, loop=0, quality=quality, method=1)
            return buffer.tell()

        low, high = size(25), size(75)
        self.assertLess(low, high)
        limit = (low + high) // 2
        renderer = self.make_renderer()
        renderer.settings = render.Settings(max_webp_bytes=limit, fps=12)
        data = renderer.fit_animation(frames, 75, 1, "t.webp")
        self.assertLessEqual(len(data), limit)
        self.assertGreater(len(data), low)

    def test_valid_existing_flags_truncated_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = touch(Path(tmp) / "a.png", b"not a png")
            with self.assertRaises(MediaError):
                render.valid_existing(bad)
            self.assertFalse(render.valid_existing(Path(tmp) / "missing.png"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
class EndToEndTests(unittest.TestCase):
    def test_pack_generated_and_rerun_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=12",
                            "-pix_fmt", "yuv420p", str(video)], check=True)
            args = [str(video), "--quiet", "--seconds", "1", "--fps", "8"]
            self.assertEqual(cli.main(args), 0)
            scr = Path(tmp) / "scr"
            names = sorted(p.name for p in scr.iterdir())
            self.assertIn("sheet_clip.png", names)
            self.assertIn("center1.webp", names)
            self.assertIn("screen.png", names)
            self.assertTrue(any(n.startswith("centerlongest_") for n in names))
            before = (scr / "sheet_clip.png").stat().st_mtime_ns
            self.assertEqual(cli.main(args), 0)
            self.assertEqual((scr / "sheet_clip.png").stat().st_mtime_ns, before)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
class AvifEndToEndTests(unittest.TestCase):
    def test_avif_pack_generated_readable_and_under_limit(self):
        try:
            render.check_avif()
        except MediaError:
            self.skipTest("Pillow cannot write animated AVIF")
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=12",
                            "-pix_fmt", "yuv420p", str(video)], check=True)
            args = [str(video), "--quiet", "--seconds", "1", "--fps", "8", "--format", "avif", "--max-webp-mib", "0.5"]
            self.assertEqual(cli.main(args), 0)
            scr = Path(tmp) / "scr"
            names = sorted(p.name for p in scr.iterdir())
            self.assertIn("center1.avif", names)
            self.assertTrue(any(n.startswith("centerlongest_") and n.endswith(".avif") for n in names))
            self.assertFalse(any(n.endswith(".webp") for n in names))
            for animation in scr.glob("*.avif"):
                self.assertLessEqual(animation.stat().st_size, 512 * 1024)
                self.assertTrue(render.valid_existing(animation))
            before = (scr / "center1.avif").stat().st_mtime_ns
            self.assertEqual(cli.main(args), 0)
            self.assertEqual((scr / "center1.avif").stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
