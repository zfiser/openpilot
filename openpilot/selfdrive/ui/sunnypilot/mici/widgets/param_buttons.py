"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.selfdrive.ui.sunnypilot.mici.widgets.choices import Choice, label_for, next_choice, with_current
from openpilot.system.ui.lib.application import MousePos


class BigChoiceParam(BigButton):
  """A button for an integer setting: it shows the current choice under the title and steps to the next one on every tap."""

  def __init__(self, text: str, param: str, choices: list[Choice]):
    super().__init__(text, "")
    self._param = param
    self._params = Params()
    self._base_choices = choices
    self._choices = list(choices)
    self.refresh()

  def _current(self) -> int | None:
    try:
      value = self._params.get(self._param, return_default=True)
      return None if value is None else int(float(value))
    except Exception:
      return None

  def refresh(self) -> None:
    current = self._current()
    self._choices = with_current(self._base_choices, current)
    self.set_value(label_for(self._choices, current))

  def _handle_mouse_release(self, mouse_pos: MousePos) -> None:
    super()._handle_mouse_release(mouse_pos)
    value, label = next_choice(self._choices, self._current())
    self._params.put(self._param, value, block=True)
    self.set_value(label)
