"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from collections import deque

LEAD_DISTANCE_KEY = "lead_distance"  # carData item filled by the brand specific car state extension
RAW_DISTANCE_KEY = "radar_distance"  # the radar's raw lead (0.05 m, 50 Hz) where the car sends it, used first
DECIMAL_BELOW = 10.0  # m, closer than this the distance shows one decimal
HYSTERESIS = 0.1  # m, the shown decimal changes only after the value moved this much (no flicker of the last digit)
TREND_WINDOW = 1.0  # s, the distance is compared with the one this long ago
TREND_THRESHOLD = 1.0  # m, the car reports whole metres at 5 Hz, one metre of change in the window is noise at most
CLOSING, STABLE, OPENING = -1, 0, 1


def lead_distance(sm, started_frame: int) -> float | None:
  """Distance to the lead in metres from the car's radar: the raw radar item when the car sends it, else the dashboard
  number. None when there is no lead or no such item."""
  try:
    if sm.recv_frame["carStateSP"] < started_frame:
      return None
    dashboard = None
    for item in sm["carStateSP"].carData:
      if item.key == RAW_DISTANCE_KEY:
        return float(item.value) if item.valid else None
      if item.key == LEAD_DISTANCE_KEY:
        dashboard = float(item.value) if item.valid else None
    return dashboard
  except Exception:
    pass
  return None


class DistanceText:
  """The distance as shown: one decimal below DECIMAL_BELOW, whole metres above. The decimal follows with HYSTERESIS."""

  def __init__(self):
    self._shown: float | None = None

  def update(self, distance: float | None) -> str | None:
    if distance is None:
      self._shown = None
      return None
    if distance >= DECIMAL_BELOW:
      self._shown = None
      return str(int(round(distance)))
    if self._shown is None or abs(distance - self._shown) >= HYSTERESIS:
      self._shown = round(distance, 1)
    return f"{self._shown:.1f}"


class LeadTrend:
  """Tells whether the gap to the lead is getting smaller, bigger or about the same over the last second."""

  def __init__(self, window: float = TREND_WINDOW, threshold: float = TREND_THRESHOLD):
    self._window = window
    self._threshold = threshold
    self._history: deque[tuple[float, float]] = deque()

  def update(self, distance: float | None, now: float) -> int:
    if distance is None:
      self._history.clear()  # a new lead starts without a trend
      return STABLE
    self._history.append((now, distance))
    # keep one sample at or before the window start to compare against
    while len(self._history) > 1 and self._history[1][0] <= now - self._window:
      self._history.popleft()
    oldest_time, oldest = self._history[0]
    if now - oldest_time < self._window * 0.5:
      return STABLE  # not enough history yet
    change = distance - oldest
    if change <= -self._threshold:
      return CLOSING
    if change >= self._threshold:
      return OPENING
    return STABLE
