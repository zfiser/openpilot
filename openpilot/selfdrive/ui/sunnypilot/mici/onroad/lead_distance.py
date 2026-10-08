"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from collections import deque

LEAD_DISTANCE_KEY = "lead_distance"  # carData item filled by the brand specific car state extension
TREND_WINDOW = 1.0  # s, the distance is compared with the one this long ago
TREND_THRESHOLD = 1.0  # m, the car reports whole metres at 5 Hz, one metre of change in the window is noise at most
CLOSING, STABLE, OPENING = -1, 0, 1


def lead_distance(sm, started_frame: int) -> int | None:
  """Distance to the lead in metres as reported by the car's radar, None when there is no lead or no such item."""
  try:
    if sm.recv_frame["carStateSP"] < started_frame:
      return None
    for item in sm["carStateSP"].carData:
      if item.key == LEAD_DISTANCE_KEY:
        return int(round(item.value)) if item.valid else None
  except Exception:
    pass
  return None


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
