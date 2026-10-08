"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import os

import pyray as rl

TRIGGER = "/tmp/ui_screenshot_request"
OUTPUT = "/tmp/ui_screenshot.png"


class ScreenshotOnRequest:
  """Saves the frame that is being drawn to OUTPUT when the TRIGGER file exists, for looking at the real screen over adb:

    touch /tmp/ui_screenshot_request; sleep 2; adb pull /tmp/ui_screenshot.png

  Call update() once per frame at the end of the frame, when everything has been drawn."""

  def __init__(self, check_every: int = 10, trigger: str = TRIGGER, output: str = OUTPUT):
    self._check_every = check_every
    self._trigger = trigger
    self._output = output
    self._frame = 0

  def update(self) -> bool:
    """True when a screenshot was written this frame."""
    self._frame += 1
    if self._frame % self._check_every or not os.path.exists(self._trigger):
      return False
    try:
      os.remove(self._trigger)
    except OSError:
      return False

    image = rl.load_image_from_screen()
    try:
      tmp = self._output + ".tmp.png"
      saved = bool(rl.export_image(image, tmp))
      if saved:
        os.replace(tmp, self._output)  # the file appears complete or not at all
      return saved
    finally:
      rl.unload_image(image)
