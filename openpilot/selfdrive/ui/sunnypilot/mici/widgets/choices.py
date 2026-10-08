"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

Choice = tuple[int, str]  # (value stored in the param, text shown)


def with_current(choices: list[Choice], current: int | None) -> list[Choice]:
  """The choices, plus the stored value when it is not one of them (set elsewhere), so tapping never loses it silently."""
  if current is None or any(value == current for value, _ in choices):
    return list(choices)
  return [*choices, (current, str(current))]


def label_for(choices: list[Choice], current: int | None) -> str:
  for value, label in choices:
    if value == current:
      return label
  return str(current) if current is not None else "--"


def next_choice(choices: list[Choice], current: int | None) -> Choice:
  """The choice after the current one, wrapping around. An unknown current value goes to the first choice."""
  for i, (value, _) in enumerate(choices):
    if value == current:
      return choices[(i + 1) % len(choices)]
  return choices[0]
