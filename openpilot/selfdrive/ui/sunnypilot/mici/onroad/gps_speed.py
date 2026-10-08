"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
MS_TO_KPH = 3.6
MS_TO_MPH = 2.2369363
GPS_SERVICES = ("gpsLocationExternal", "gpsLocation")  # external u-blox first, then the modem's receiver
STANDSTILL_NOISE = 0.5  # m/s, a stopped receiver still reports a little speed


def gps_speed(sm, is_metric: bool) -> int | None:
  """GPS speed in km/h or mph, rounded, None without a fix (and while the receiver is not publishing)."""
  for service in GPS_SERVICES:
    try:
      if not sm.alive[service]:
        continue
      gps = sm[service]
      if not gps.hasFix:
        continue
      speed = float(gps.speed)
    except Exception:
      continue
    if speed < STANDSTILL_NOISE:
      speed = 0.0
    return round(speed * (MS_TO_KPH if is_metric else MS_TO_MPH))
  return None
