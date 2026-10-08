"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.selfdrive.car.raw_can_watch import PARAM, RELOAD_SECONDS, RawCanWatch, decode, extract_bits, parse_watches


class FakeParams:
  def __init__(self, config=None):
    self.config = config

  def get(self, key):
    assert key == PARAM
    return self.config


class Clock:
  def __init__(self):
    self.t = 100.0

  def __call__(self):
    return self.t


def watch(**kw):
  entry = {"label": "w", "address": 0x3A6, "start_bit": 0, "length": 16, "little_endian": True, "unit": "kPa"}
  entry.update(kw)
  return entry


def frame(address, data, bus=0):
  return (0, [(address, bytes(data), bus)])


class TestExtractBits:
  def test_little_endian_matches_dbc(self):
    # 0x3A6 as seen in the recording, four little endian 16 bit values
    data = bytes.fromhex("0801080108010801")
    assert [extract_bits(data, s, 16, True) for s in (0, 16, 32, 48)] == [264] * 4

  def test_little_endian_unaligned(self):
    assert extract_bits(bytes([0b10110100, 0]), 2, 4, True) == 0b1101

  def test_big_endian_matches_dbc(self):
    # DBC "7|16@0+" is bytes 0 and 1, high byte first
    assert extract_bits(bytes([0x03, 0xFF, 0, 0, 0, 0, 0, 0]), 7, 16, False) == 0x03FF

  def test_big_endian_odometer_layout(self):
    # UI_SETTING.ODOMETER is 39|32@0+ (bytes 4 to 7, high byte first)
    data = bytes([0, 0, 0, 0]) + (123456).to_bytes(4, "big")
    assert extract_bits(data, 39, 32, False) == 123456

  def test_big_endian_single_byte_and_nibble(self):
    assert extract_bits(bytes([0xAB, 0xCD]), 15, 8, False) == 0xCD
    assert extract_bits(bytes([0xAB]), 7, 4, False) == 0xA


class TestDecode:
  def entry(self, **kw):
    return parse_watches([watch(**kw)])[0]

  def test_scale_and_offset(self):
    assert decode(bytes([65, 0]), self.entry(length=8, scale=1.0, offset=-40)) == 25
    assert decode(bytes([100, 0]), self.entry(length=8, scale=0.5)) == 50

  def test_signed(self):
    assert decode(bytes([0xFF, 0xFF]), self.entry(signed=True)) == -1
    assert decode(bytes([0xFF, 0xFF]), self.entry(signed=False)) == 65535
    assert decode(bytes([0xFE]), self.entry(length=8, signed=True)) == -2


class TestParse:
  def test_hex_string_address_and_defaults(self):
    w = parse_watches([{"address": "0x3A6"}])[0]
    assert w["address"] == 0x3A6 and w["length"] == 8 and w["bus"] == 0 and w["little_endian"] and w["label"] == "0x3A6"

  def test_bad_entries_are_skipped(self):
    config = [{"label": "no address"}, watch(length=0), watch(length=65), watch(start_bit=60, length=16), watch(address=-1), "text", None, watch()]
    assert len(parse_watches(config)) == 1

  def test_not_a_list(self):
    for config in (None, {}, "x", 5):
      assert parse_watches(config) == []

  def test_limit(self):
    assert len(parse_watches([watch() for _ in range(50)])) == 32


class TestRawCanWatch:
  def test_no_config_no_items(self):
    w = RawCanWatch(FakeParams(None), now=Clock())
    assert w.update([frame(0x3A6, [8, 1, 8, 1, 8, 1, 8, 1])]) == []

  def test_decodes_a_watch(self):
    w = RawCanWatch(FakeParams([watch(label="Tire pressure?")]), now=Clock())
    items = w.update([frame(0x3A6, [8, 1, 8, 1, 8, 1, 8, 1])])
    assert len(items) == 1 and items[0].label == "Tire pressure?" and items[0].value == 264 and items[0].unit == "kPa" and items[0].valid

  def test_no_item_until_the_message_is_seen(self):
    w = RawCanWatch(FakeParams([watch()]), now=Clock())
    assert w.update([frame(0x123, [0] * 8)]) == []

  def test_keeps_the_last_value_between_frames(self):
    w = RawCanWatch(FakeParams([watch()]), now=Clock())
    w.update([frame(0x3A6, [8, 1, 0, 0, 0, 0, 0, 0])])
    assert w.update([])[0].value == 264
    assert w.update([frame(0x3A6, [10, 1, 0, 0, 0, 0, 0, 0])])[0].value == 266

  def test_bus_filter(self):
    w = RawCanWatch(FakeParams([watch(bus=2)]), now=Clock())
    assert w.update([frame(0x3A6, [8, 1] + [0] * 6, bus=0)]) == []
    assert len(w.update([frame(0x3A6, [8, 1] + [0] * 6, bus=2)])) == 1
    w = RawCanWatch(FakeParams([watch(bus=-1)]), now=Clock())
    assert len(w.update([frame(0x3A6, [8, 1] + [0] * 6, bus=1)])) == 1

  def test_short_frame_is_ignored_not_crashing(self):
    w = RawCanWatch(FakeParams([watch(start_bit=48, length=16)]), now=Clock())
    assert w.update([frame(0x3A6, [8, 1, 8, 1])]) == []

  def test_two_watches_on_one_message(self):
    cfg = [watch(label="a", start_bit=0), watch(label="b", start_bit=16)]
    items = RawCanWatch(FakeParams(cfg), now=Clock()).update([frame(0x3A6, [8, 1, 9, 1, 0, 0, 0, 0])])
    assert [(i.label, i.value) for i in items] == [("a", 264), ("b", 265)]

  def test_config_changes_are_picked_up_after_a_while(self):
    params, clock = FakeParams([watch(label="a")]), Clock()
    w = RawCanWatch(params, now=clock)
    f = frame(0x3A6, [8, 1] + [0] * 6)
    assert w.update([f])[0].label == "a"
    params.config = [watch(label="b")]
    assert w.update([f])[0].label == "a"  # not re-read yet
    clock.t += RELOAD_SECONDS + 0.1
    assert w.update([f])[0].label == "b"
    params.config = None
    clock.t += RELOAD_SECONDS + 0.1
    assert w.update([f]) == []

  def test_broken_params_do_not_raise(self):
    class Broken:
      def get(self, key):
        raise RuntimeError("no params")
    assert RawCanWatch(Broken(), now=Clock()).update([frame(0x3A6, [0] * 8)]) == []
