"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import time
from collections.abc import Callable

GPS_SPEED, LEAD_DISTANCE, BRAKE_DOT, RPM = "ShowGpsSpeed", "ShowLeadDistance", "ShowBrakeDot", "ShowRpm"
KEYS = (GPS_SPEED, LEAD_DISTANCE, BRAKE_DOT, RPM)
REFRESH_SECONDS = 1.0  # the settings are read this often instead of on every frame


class DisplayOptions:
  """Which extra items the driving screen draws, from the on/off settings in the toggles menu. On unless switched off."""

  def __init__(self, params, now: Callable[[], float] = time.monotonic):
    self._params = params
    self._now = now
    self._next = float("-inf")
    self._values = dict.fromkeys(KEYS, True)

  def enabled(self, key: str) -> bool:
    if self._now() >= self._next:
      self._next = self._now() + REFRESH_SECONDS
      for k in KEYS:
        try:
          self._values[k] = bool(self._params.get(k, return_default=True))  # on until switched off, unset means the default
        except Exception:
          self._values[k] = True
    return self._values.get(key, True)
