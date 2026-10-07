#!/usr/bin/env python3
"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Manage the RawCanWatch setting: raw CAN fields shown as tiles on the car data page.

  raw_can_watch.py list
  raw_can_watch.py add --label "Tire FL" --address 0x3A6 --start-bit 0 --length 16 --unit kPa
  raw_can_watch.py add --label Temp --address 0x3A7 --start-bit 7 --length 16 --big-endian --offset -40 --unit C
  raw_can_watch.py remove 0
  raw_can_watch.py clear

Bit numbering is the same as a DBC signal: little endian counts from the lowest bit, big endian start bit is the most
significant bit (7|16 means bytes 0 and 1, high byte first). Changes appear on the screen within a couple of seconds.
"""
import argparse
import json

from openpilot.common.params import Params

PARAM = "RawCanWatch"


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = parser.add_subparsers(dest="cmd", required=True)
  sub.add_parser("list")
  sub.add_parser("clear")
  rm = sub.add_parser("remove")
  rm.add_argument("index", type=int)
  add = sub.add_parser("add")
  add.add_argument("--label", required=True)
  add.add_argument("--address", required=True, help="CAN address, decimal or 0x hex")
  add.add_argument("--bus", type=int, default=0, help="0 is the car, 2 the camera side, -1 any (default 0)")
  add.add_argument("--start-bit", type=int, default=0)
  add.add_argument("--length", type=int, default=8)
  add.add_argument("--big-endian", action="store_true")
  add.add_argument("--signed", action="store_true")
  add.add_argument("--scale", type=float, default=1.0)
  add.add_argument("--offset", type=float, default=0.0)
  add.add_argument("--unit", default="")
  args = parser.parse_args()

  params = Params()
  watches = params.get(PARAM)
  if not isinstance(watches, list):
    watches = []

  if args.cmd == "add":
    watches.append({"label": args.label, "address": args.address, "bus": args.bus, "start_bit": args.start_bit,
                    "length": args.length, "little_endian": not args.big_endian, "signed": args.signed,
                    "scale": args.scale, "offset": args.offset, "unit": args.unit})
  elif args.cmd == "remove":
    if not 0 <= args.index < len(watches):
      raise SystemExit(f"no watch with index {args.index}")
    watches.pop(args.index)
  elif args.cmd == "clear":
    watches = []

  if args.cmd in ("add", "remove", "clear"):
    params.put(PARAM, watches, block=True)
  for i, w in enumerate(watches):
    print(i, json.dumps(w))
  if not watches:
    print("no watches")


if __name__ == "__main__":
  main()
