"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import time
from collections.abc import Callable

from opendbc.sunnypilot.car.car_data import make_car_data_item

PARAM = "RawCanWatch"
MAX_WATCHES = 12
RELOAD_SECONDS = 2.0


def extract_bits(data: bytes, start_bit: int, length: int, little_endian: bool) -> int:
  """Same meaning as a DBC signal. Little endian: start_bit is the lowest bit (counted from bit 0 of byte 0).
  Big endian: start_bit is the highest bit, so 7|16 are bytes 0 and 1, most significant byte first."""
  if little_endian:
    return (int.from_bytes(data, "little") >> start_bit) & ((1 << length) - 1)
  value = 0
  byte, bit = divmod(start_bit, 8)
  for _ in range(length):
    value = (value << 1) | ((data[byte] >> bit) & 1)
    if bit == 0:
      byte, bit = byte + 1, 7
    else:
      bit -= 1
  return value


def decode(data: bytes, watch: dict) -> float:
  raw = extract_bits(data, watch["start_bit"], watch["length"], watch["little_endian"])
  if watch["signed"] and raw >= 1 << (watch["length"] - 1):
    raw -= 1 << watch["length"]
  return raw * watch["scale"] + watch["offset"]


def parse_watches(config) -> list[dict]:
  """Entries of the RawCanWatch setting, anything malformed is skipped. Example entry:
  {"label": "Tire FL", "address": "0x3A6", "bus": 0, "start_bit": 0, "length": 16, "little_endian": true,
   "signed": false, "scale": 1.0, "offset": 0.0, "unit": "kPa"}"""
  watches = []
  if not isinstance(config, list):
    return watches
  for i, entry in enumerate(config[:MAX_WATCHES]):
    try:
      address = entry["address"]
      address = int(address, 0) if isinstance(address, str) else int(address)
      length = int(entry.get("length", 8))
      start_bit = int(entry.get("start_bit", 0))
      little_endian = bool(entry.get("little_endian", True))
      if not 1 <= length <= 64 or not 0 <= start_bit < 64 or address < 0:
        continue
      if little_endian and start_bit + length > 64:
        continue
      watches.append({
        "key": f"watch_{i}",
        "label": str(entry.get("label", f"0x{address:X}"))[:24],
        "address": address,
        "bus": int(entry.get("bus", 0)),   # -1 means any bus
        "start_bit": start_bit,
        "length": length,
        "little_endian": little_endian,
        "signed": bool(entry.get("signed", False)),
        "scale": float(entry.get("scale", 1.0)),
        "offset": float(entry.get("offset", 0.0)),
        "unit": str(entry.get("unit", ""))[:8],
      })
    except Exception:
      continue
  return watches


class RawCanWatch:
  """Decodes configured fields of raw CAN frames into car data tiles, to try out guesses without rebuilding.
  The setting is re-read every couple of seconds, so changes show up on the car data page on their own."""

  def __init__(self, params, now: Callable[[], float] = time.monotonic):
    self._params = params
    self._now = now
    self._next_reload = 0.0
    self._watches: list[dict] = []
    self._by_address: dict[int, list[dict]] = {}
    self._last: dict[str, float] = {}

  def _reload(self) -> None:
    try:
      watches = parse_watches(self._params.get(PARAM))
    except Exception:
      watches = []
    if watches != self._watches:
      self._watches = watches
      self._by_address = {}
      for w in watches:
        self._by_address.setdefault(w["address"], []).append(w)
      self._last = {k: v for k, v in self._last.items() if k in {w["key"] for w in watches}}

  def update(self, can_list) -> list:
    """can_list is the list of (timestamp, [(address, data, bus), ...]) the car process receives. Returns one item per
    watch that has seen its message at least once."""
    if self._now() >= self._next_reload:
      self._next_reload = self._now() + RELOAD_SECONDS
      self._reload()
    if not self._watches:
      return []

    for _, frames in can_list:
      for address, data, bus in frames:
        for w in self._by_address.get(address, ()):
          if w["bus"] in (-1, bus) and len(data) * 8 >= w["start_bit"] + (w["length"] if w["little_endian"] else 1):
            try:
              self._last[w["key"]] = decode(bytes(data), w)
            except Exception:
              pass

    return [make_car_data_item(w["key"], w["label"], self._last[w["key"]], w["unit"])
            for w in self._watches if w["key"] in self._last]
