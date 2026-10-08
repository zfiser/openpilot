"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "screenshot.py"


def _load(rl):
  with mock.patch.dict(sys.modules, {"pyray": rl}):
    spec = importlib.util.spec_from_file_location("screenshot_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
  return module


class TestScreenshot(unittest.TestCase):
  def setUp(self):
    self.dir = tempfile.TemporaryDirectory()
    self.trigger = str(Path(self.dir.name) / "request")
    self.output = str(Path(self.dir.name) / "out.png")
    self.rl = mock.MagicMock()
    self.rl.export_image.side_effect = lambda image, path: Path(path).write_bytes(b"png") or True
    self.shot = _load(self.rl).ScreenshotOnRequest(check_every=1, trigger=self.trigger, output=self.output)

  def tearDown(self):
    self.dir.cleanup()

  def test_nothing_without_a_trigger(self):
    assert not self.shot.update()
    self.rl.load_image_from_screen.assert_not_called()
    assert not Path(self.output).exists()

  def test_one_screenshot_per_trigger(self):
    Path(self.trigger).touch()
    assert self.shot.update()
    assert Path(self.output).read_bytes() == b"png"
    assert not Path(self.trigger).exists()
    assert not Path(self.output + ".tmp.png").exists()
    assert not self.shot.update()  # trigger is gone, no second shot
    assert self.rl.load_image_from_screen.call_count == 1
    self.rl.unload_image.assert_called_once()

  def test_checks_only_every_nth_frame(self):
    shot = _load(self.rl).ScreenshotOnRequest(check_every=5, trigger=self.trigger, output=self.output)
    Path(self.trigger).touch()
    results = [shot.update() for _ in range(5)]
    assert results == [False, False, False, False, True]

  def test_failed_export_leaves_no_output(self):
    self.rl.export_image.side_effect = lambda image, path: False
    Path(self.trigger).touch()
    assert not self.shot.update()
    assert not Path(self.output).exists()
    self.rl.unload_image.assert_called_once()


if __name__ == "__main__":
  unittest.main()
