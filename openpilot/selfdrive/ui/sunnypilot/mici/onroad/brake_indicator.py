"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
FRICTION_BRAKE_KEY = "friction_brake_force"  # carData item, newtons applied by the friction brakes (0 while only regen slows the car)


def friction_braking(sm, started_frame: int) -> bool:
  """True while the car reports force on the friction brakes, False for regen or no braking, and without the item."""
  try:
    if sm.recv_frame["carStateSP"] < started_frame:
      return False
    for item in sm["carStateSP"].carData:
      if item.key == FRICTION_BRAKE_KEY:
        return bool(item.valid and item.value > 0)
  except Exception:
    pass
  return False
