"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""


def find_rpm(sm, started_frame: int) -> float | None:
  """Engine RPM from the brand specific car data of the current drive, None when the car does not report it."""
  try:
    if sm.recv_frame["carStateSP"] < started_frame:
      return None
    for item in sm["carStateSP"].carData:
      if item.key == "rpm":
        return float(item.value) if item.valid else None
  except Exception:
    pass
  return None


def format_rpm(rpm: float | None) -> str | None:
  """The number shown on the driving screen (the unit is drawn separately), None while the engine is off or unknown."""
  if rpm is None:
    return None
  rounded = round(rpm / 10) * 10  # the last digit only jitters
  if rounded <= 0:
    return None
  return f"{rounded:,}"
