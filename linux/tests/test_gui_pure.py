"""Tests for the pure helpers in the Windows GUI script.

The script cannot be imported by name (its filename has a space and a curly apostrophe) and it imports
tkinter, OpenCV and other desktop packages at the top level. It is therefore loaded by path, and any
module that is not installed (typically on Linux CI) is replaced by a stub so the pure helpers can run.

Environment variables:
  THUMB_IT_REPO       repository root, when the tests were copied away from linux/tests (CI does this)
  REQUIRE_GUI_TESTS   make "GUI script could not be loaded" a failure instead of a skip
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageFilter


def find_script():
    roots = [os.environ.get("THUMB_IT_REPO"), os.environ.get("GITHUB_WORKSPACE")]
    here = Path(__file__).resolve()
    roots += [str(p) for p in here.parents[:4]]
    for root in roots:
        if root:
            matches = sorted(Path(root).glob("Pumpkin*Thumb It 5.2.py"))
            if matches:
                return matches[0]
    return None


def load_gui():
    script = find_script()
    if script is None:
        return None, None, "GUI script not found (set THUMB_IT_REPO)"
    stubbed = []
    try:
        for _ in range(20):
            try:
                spec = importlib.util.spec_from_file_location("thumb_it_gui", script)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module, script, ""
            except ImportError as exc:  # tkinter, cv2, tkinterdnd2, requests, ... missing on this machine
                name = getattr(exc, "name", None)
                if not name or name in stubbed:
                    raise
                sys.modules[name] = mock.MagicMock(name=name)
                stubbed.append(name)
        return None, script, "too many missing modules"
    except Exception as exc:
        return None, script, f"GUI could not be loaded: {exc!r}"
    finally:
        for name in stubbed:
            sys.modules.pop(name, None)


GUI, SCRIPT, REASON = load_gui()


class GuiAvailabilityTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("REQUIRE_GUI_TESTS"), "REQUIRE_GUI_TESTS not set")
    def test_gui_loaded_when_required(self):
        self.assertIsNotNone(GUI, REASON)


@unittest.skipIf(GUI is None, REASON)
class GuiPureTests(unittest.TestCase):
    def search(self, limit, start=75, floor=25):
        calls = []

        def encode(quality):
            calls.append(quality)
            return b"x" * (quality * 100)

        return GUI._fit_webp_quality(encode, limit, start, floor), calls

    def test_fits_first_try(self):
        data, calls = self.search(10000)
        self.assertEqual((len(data) // 100, calls), (75, [75]))

    def test_highest_fitting_quality(self):
        data, _ = self.search(6234)
        self.assertEqual(len(data) // 100, 62)

    def test_floor_fits_exactly(self):
        data, _ = self.search(2500)
        self.assertEqual(len(data) // 100, 25)

    def test_over_limit_at_floor_raises(self):
        with self.assertRaises(GUI.AnimationTooLarge):
            self.search(2499)

    def test_start_at_floor_over_limit_raises(self):
        with self.assertRaises(GUI.AnimationTooLarge):
            self.search(100, start=25)

    def test_stable_seed(self):
        path = "C:\\videos\\a.mp4"
        self.assertEqual(GUI._stable_seed(path), GUI._stable_seed(path))
        self.assertNotEqual(GUI._stable_seed(path), GUI._stable_seed(path + "x"))
        self.assertTrue(0 <= GUI._stable_seed(path) < 2 ** 32)
        code = ("import importlib.util,sys;from unittest import mock;"
                "[sys.modules.setdefault(n, mock.MagicMock()) for n in sys.argv[3:]];"
                "s=importlib.util.spec_from_file_location('g',sys.argv[1]);m=importlib.util.module_from_spec(s);"
                "s.loader.exec_module(m);print(m._stable_seed(sys.argv[2]))")
        def missing(name):
            try:
                return importlib.util.find_spec(name.split(".")[0]) is None
            except (ImportError, ValueError):
                return True

        optional = [n for n in ("cv2", "numpy", "requests", "tkinterdnd2", "tkinter", "tkinter.ttk",
                                "tkinter.filedialog", "tkinter.messagebox", "psutil") if missing(n)]
        other = subprocess.run([sys.executable, "-c", code, str(SCRIPT), path, *optional],
                               capture_output=True, text=True)
        self.assertEqual(other.stdout.strip(), str(GUI._stable_seed(path)), other.stderr)

    def test_quality_range_webp_caps_and_falls_back(self):
        with mock.patch.object(GUI, "ANIM_FORMAT", "webp"):
            self.assertEqual(GUI._animation_quality_range({"WEBP_QUALITY": 85}),
                             (min(85, GUI.PROXY_SAFE_WEBP_QUALITY_CAP), GUI.MIN_WEBP_QUALITY))
            self.assertEqual(GUI._animation_quality_range({}, 0)[0], min(80, GUI.PROXY_SAFE_WEBP_QUALITY_CAP))

    def test_quality_range_avif_constants(self):
        with mock.patch.object(GUI, "ANIM_FORMAT", "avif"):
            self.assertEqual(GUI._animation_quality_range({"WEBP_QUALITY": 10}),
                             (GUI.AVIF_START_QUALITY, GUI.AVIF_MIN_QUALITY))

    def test_extension_follows_format(self):
        with mock.patch.object(GUI, "ANIM_FORMAT", "avif"):
            self.assertEqual(GUI._anim_ext(), ".avif")
        with mock.patch.object(GUI, "ANIM_FORMAT", "webp"):
            self.assertEqual(GUI._anim_ext(), ".webp")

    def test_atomic_write_leaves_only_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out.webp")
            GUI._write_bytes_atomic(target, b"abc")
            self.assertEqual(os.listdir(tmp), ["out.webp"])
            self.assertEqual(Path(target).read_bytes(), b"abc")

    def test_atomic_write_cleans_up_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out.webp")
            with mock.patch("os.replace", side_effect=OSError("nope")):
                with self.assertRaises(OSError):
                    GUI._write_bytes_atomic(target, b"abc")
            self.assertEqual(os.listdir(tmp), [])

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_atomic_write_honours_umask(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(GUI, "_UMASK", 0o077):
            target = os.path.join(tmp, "out.webp")
            GUI._write_bytes_atomic(target, b"abc")
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(GUI, "_UMASK", 0o022):
            target = os.path.join(tmp, "out.webp")
            GUI._write_bytes_atomic(target, b"abc")
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o644)

    def test_failed_probe_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.mp4")
            Path(path).write_bytes(b"x")
            zero = {"duration": 0.0}
            good = {"duration": 5.0}
            GUI._INFO_CACHE.clear()
            with mock.patch.object(GUI, "_probe_video_info", side_effect=[zero, good, good]) as probe:
                self.assertEqual(GUI.get_video_info(path)["duration"], 0.0)
                self.assertEqual(GUI.get_video_info(path)["duration"], 5.0)
                self.assertEqual(GUI.get_video_info(path)["duration"], 5.0)
                self.assertEqual(probe.call_count, 2)

    def test_failure_report_ignored_while_stopping(self):
        seen = []
        GUI.set_failure_sink(seen.append)
        self.addCleanup(GUI.set_failure_sink, None)
        GUI._report_failure("thing", RuntimeError("boom"))
        self.assertEqual(seen, ["thing failed: boom"])
        GUI.STOP_EVENT.set()
        self.addCleanup(GUI.STOP_EVENT.clear)
        GUI._report_failure("thing", RuntimeError("stopped"))
        self.assertEqual(len(seen), 1)


@unittest.skipIf(GUI is None, REASON)
class GuiClipTests(unittest.TestCase):
    W, H = 8, 6

    def frames(self, n):
        return [Image.new("RGB", (self.W, self.H), (i, i, i)) for i in range(n)]

    def clip(self, ts, decoded):
        with mock.patch.object(GUI, "_decode_clip_frames", return_value=decoded) as decode, \
                mock.patch.object(GUI, "_ffmpeg_extract_frame_pil_scaled",
                                  side_effect=lambda *a: Image.new("RGB", (self.W, self.H), (200, 0, 0))) as single:
            result = GUI._slot_clip_frames("v.mp4", ts, self.W, self.H)
        return result, decode, single

    def test_exact_decode_is_used_as_is(self):
        decoded = self.frames(5)
        result, decode, single = self.clip([0, 1, 2, 3, 4], decoded)
        self.assertEqual([f.getpixel((0, 0))[0] for f in result], [0, 1, 2, 3, 4])
        decode.assert_called_once()
        single.assert_not_called()

    def test_short_decode_is_padded_with_last_frame(self):
        result, _, single = self.clip([0, 1, 2, 3, 4], self.frames(3))
        self.assertEqual([f.getpixel((0, 0))[0] for f in result], [0, 1, 2, 2, 2])
        single.assert_not_called()

    def test_long_decode_is_truncated(self):
        result, _, _ = self.clip([0, 1, 2], self.frames(6))
        self.assertEqual(len(result), 3)

    def test_failed_decode_falls_back_to_per_frame_grabs(self):
        result, _, single = self.clip([0, 1, 2], [])
        self.assertEqual(len(result), 3)
        self.assertEqual(single.call_count, 3)
        self.assertEqual(result[0].getpixel((0, 0)), (200, 0, 0))

    def test_tiny_span_skips_clip_decode(self):
        result, decode, single = self.clip([5.0, 5.05, 5.1], self.frames(3))
        decode.assert_not_called()
        self.assertEqual(single.call_count, 3)
        self.assertEqual(len(result), 3)

    def test_per_frame_fallback_uses_black_when_grab_fails(self):
        with mock.patch.object(GUI, "_decode_clip_frames", return_value=[]), \
                mock.patch.object(GUI, "_ffmpeg_extract_frame_pil_scaled", return_value=None):
            result = GUI._slot_clip_frames("v.mp4", [0, 1], self.W, self.H)
        self.assertEqual([f.size for f in result], [(self.W, self.H)] * 2)

    def test_stop_aborts_fallback(self):
        GUI.STOP_EVENT.set()
        self.addCleanup(GUI.STOP_EVENT.clear)
        with mock.patch.object(GUI, "_decode_clip_frames", return_value=[]):
            with self.assertRaises(RuntimeError):
                GUI._slot_clip_frames("v.mp4", [0.0, 1.0], self.W, self.H)


@unittest.skipIf(GUI is None, REASON)
class GuiPasteGoldenTests(unittest.TestCase):
    """The cached mask/shadow must give pixel-identical results to the original per-call code."""

    def reference(self, sheet, thumb, slot):
        x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
        thumb = thumb.resize((w, h), Image.LANCZOS).convert("RGBA")
        radius = max(1, int(GUI.ROUND_RADIUS_BIG if slot.get("is_big") else GUI.ROUND_RADIUS_SMALL))
        mask = GUI._rounded_mask((w, h), radius)
        thumb.putalpha(mask)
        sx, sy = x + int(GUI.SHADOW_OFFSET[0]), y + int(GUI.SHADOW_OFFSET[1])
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, int(GUI.SHADOW_ALPHA)))
        shadow.putalpha(mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(GUI.SHADOW_BLUR)))
        tmp = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        tmp.paste(shadow, (sx, sy), shadow)
        sheet.alpha_composite(tmp)
        sheet.paste(thumb, (x, y), thumb)

    def check(self, slot, thumb_size, sheet_size=(160, 120)):
        thumb = Image.effect_noise(thumb_size, 60).convert("RGB")
        a = Image.new("RGBA", sheet_size, (35, 35, 35, 255))
        b = a.copy()
        GUI._paste_thumb_in_slot(a, thumb, slot)
        self.reference(b, thumb, slot)
        self.assertEqual(a.tobytes(), b.tobytes())

    def test_small_slot(self):
        self.check({"x": 10, "y": 10, "w": 40, "h": 30, "is_big": False}, (40, 30))

    def test_big_slot_with_resize(self):
        self.check({"x": 20, "y": 15, "w": 80, "h": 60, "is_big": True}, (50, 20))

    def test_slot_touching_the_edge(self):
        self.check({"x": 120, "y": 90, "w": 40, "h": 30, "is_big": False}, (40, 30))


if __name__ == "__main__":
    unittest.main()
