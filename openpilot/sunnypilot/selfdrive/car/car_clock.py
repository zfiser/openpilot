"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import time
from collections.abc import Callable

CLOCK_ADDRESS = 0x675  # Toyota, once per second on the car bus: bytes 2..7 are YY MM DD hh mm ss in BCD, UTC
MIN_YEAR, MAX_YEAR = 2024, 2099
MAX_AGE = 5.0  # seconds without a clock frame before the car clock is not trusted any more


def _bcd(byte: int) -> int | None:
  high, low = byte >> 4, byte & 15
  return high * 10 + low if high < 10 and low < 10 else None


def parse_car_time(data: bytes) -> datetime.datetime | None:
  """UTC date and time from a clock frame, None when the bytes do not look like a plausible date."""
  if len(data) < 8:
    return None
  parts = [_bcd(b) for b in data[2:8]]
  if None in parts:
    return None
  year, month, day, hour, minute, second = parts
  year += 2000
  if not MIN_YEAR <= year <= MAX_YEAR:
    return None
  try:
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.UTC)
  except ValueError:
    return None


class CarClock:
  """Date and time as the car reports it. The car keeps time on its own, so this is available when the device clock is
  not (no GPS fix, no network), for example right after the device started."""

  def __init__(self, address: int = CLOCK_ADDRESS, bus: int = 0, mono: Callable[[], float] = time.monotonic):
    self._address = address
    self._bus = bus
    self._mono = mono
    self._time: datetime.datetime | None = None
    self._received = 0.0

  def update(self, can_list) -> None:
    """can_list is the list of (timestamp, [(address, data, bus), ...]) the car process receives."""
    for _, frames in can_list:
      for address, data, bus in frames:
        if address == self._address and bus == self._bus:
          parsed = parse_car_time(bytes(data))
          if parsed is not None:
            self._time = parsed
            self._received = self._mono()

  def now(self) -> datetime.datetime | None:
    """Current time (timezone aware, UTC): the last frame plus the time since it arrived. None when not available."""
    if self._time is None:
      return None
    age = self._mono() - self._received
    if age > MAX_AGE:
      return None
    return self._time + datetime.timedelta(seconds=age)
