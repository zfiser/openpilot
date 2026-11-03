"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Upload status card for the network page: share sent, speed and time left, from the same progress files as the green line on
the home screen (see openpilot/system/loggerd/upload_progress.py).
"""
import time

from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.system.loggerd.upload_progress import UploadRate, format_bytes, format_duration, format_speed, read_totals

POLL_INTERVAL = 1.0  # s


def status_text(active: bool, done: int, total: int, speed: float | None, eta: float | None) -> tuple[str, str]:
  """(title, value line) for the card."""
  if not active:
    return "uploads", "nothing to send"
  pct = int(100 * done / total) if total > 0 else 0
  title = f"uploading {pct}%"
  if speed is None:
    return title, f"{format_bytes(max(0, total - done))} left"
  if speed <= 0 or eta is None:
    return title, "stalled"
  return title, f"{format_speed(speed)}, {format_duration(eta)}"


class UploadStatusButton(BigButton):
  def __init__(self):
    super().__init__("uploads", "nothing to send")
    self._rate = UploadRate()
    self._poll_time = float("-inf")  # read at the first frame
    self._shown: tuple[str, str] = ("uploads", "nothing to send")

  def _update_state(self):
    super()._update_state()
    now = time.monotonic()
    if now - self._poll_time < POLL_INTERVAL:
      return
    self._poll_time = now
    try:
      active, done, total = read_totals()
      speed, eta = self._rate.update(now, active, done, total)
      shown = status_text(active, done, total, speed, eta)
    except Exception:
      return
    if shown != self._shown:
      self._shown = shown
      self.set_text(shown[0])
      self.set_value(shown[1])
