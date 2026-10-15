"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from collections.abc import Callable

from openpilot.selfdrive.ui.mici.layouts.settings.toggles import TogglesLayoutMici
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.selfdrive.ui.mici.widgets.dialog import BigConfirmationDialog
from openpilot.selfdrive.ui.sunnypilot.mici.widgets.param_buttons import BigBoolParam, BigChoiceParam
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.scroller import NavScroller

ICON = "icons_mici/settings.png"
LKAS_ICON = "icons_mici/settings/device/lkas.png"

LANE_CHANGE_CHOICES = [(-1, "off"), (0, "nudge"), (1, "nudgeless"), (2, "0.5 s"), (3, "1 s"), (4, "2 s"), (5, "3 s")]
# LaneChangeSmoothing: how slowly the steering may change during a lane change, 1 is the smoothest, 10 leaves the stock limit
LANE_CHANGE_SMOOTHING_CHOICES = [(1, "1 smoothest"), (3, "3"), (5, "5 default"), (7, "7"), (9, "9"), (10, "10 stock")]
STEERING_ON_BRAKE_CHOICES = [(0, "remain active"), (1, "pause"), (2, "disengage")]
BLINKER_DELAY_CHOICES = [(0, "0 s"), (1, "1 s"), (2, "2 s"), (3, "3 s"), (5, "5 s")]
OFF_ON_CHOICES = [(0, "off"), (1, "on")]
TIMEOUT_CHOICES = [(0, "default"), (30, "30 s"), (60, "1 m"), (90, "90 s"), (120, "2 m"), (180, "3 m"), (300, "5 m")]
# OnroadScreenOffBrightness: 0 auto, 1 auto (dark), 2 screen off, above that (value - 2) * 5 percent
ONROAD_BRIGHTNESS_CHOICES = [(0, "auto"), (1, "auto dark"), (2, "screen off"), (4, "10 %"), (6, "20 %"), (8, "30 %"),
                             (12, "50 %"), (22, "100 %")]
SCREEN_SAVER_CHOICES = [(60, "1 m"), (120, "2 m"), (180, "3 m"), (300, "5 m"), (600, "10 m")]
HUG_CM_CHOICES = [(20, "20 cm"), (30, "30 cm"), (40, "40 cm"), (50, "50 cm"), (60, "60 cm"), (70, "70 cm"), (80, "80 cm"), (90, "90 cm")]
# CameraOffset in metres, positive moves the car to the left: a permanent shift of the center, in steps of 10 cm
CENTER_OFFSET_CHOICES = [(-30, "30 cm right"), (-20, "20 cm right"), (-10, "10 cm right"), (0, "none"), (10, "10 cm left"),
                         (20, "20 cm left"), (30, "30 cm left")]
# RoadEdgeMinLaneWidth in metres, choices in decimetres: an automatic lane change waits until the lane next to the car is this wide.
# On its own setting, with or without the road edge block; with it on, the road edge flag is replaced by this check.
MIN_LANE_WIDTH_CHOICES = [(0, "off"), (5, "0.5 m"), (10, "1.0 m"), (15, "1.5 m"), (20, "2.0 m"), (24, "2.4 m"), (26, "2.6 m"),
                          (28, "2.8 m"), (30, "3.0 m"), (32, "3.2 m"), (34, "3.4 m")]
BLINKER_SPEEDS = (0, 20, 30, 40, 50, 60, 80, 100)


def blinker_speed_choices(is_metric: bool) -> list[tuple[int, str]]:
  unit = "km/h" if is_metric else "mph"
  return [(speed, f"{speed} {unit}") for speed in BLINKER_SPEEDS]


class SettingsPanel(NavScroller):
  """A scrolling page of buttons that reads its settings again every time it is shown."""

  def __init__(self, widgets: list[Widget]):
    super().__init__()
    self._items = widgets
    self._scroller.add_widgets(widgets)

  def show_event(self):
    super().show_event()
    for item in self._items:
      if hasattr(item, "refresh"):
        item.refresh()


def hug_panel() -> SettingsPanel:
  return SettingsPanel([
    BigChoiceParam("hug left\nlevel 1", "HugLeft1Cm", HUG_CM_CHOICES),
    BigChoiceParam("hug left\nlevel 2", "HugLeft2Cm", HUG_CM_CHOICES),
    BigChoiceParam("hug right\nlevel 1", "HugRight1Cm", HUG_CM_CHOICES),
    BigChoiceParam("hug right\nlevel 2", "HugRight2Cm", HUG_CM_CHOICES),
    BigChoiceParam("center\nposition", "CameraOffset", CENTER_OFFSET_CHOICES, scale=0.01),
  ])


def steering_panel() -> SettingsPanel:
  return SettingsPanel([
    BigChoiceParam("steering on\nbrake", "MadsSteeringMode", STEERING_ON_BRAKE_CHOICES),
    BigBoolParam("engage with\nmain cruise", "MadsMainCruiseAllowed"),
    BigBoolParam("unified\nengagement", "MadsUnifiedEngagementMode"),
    BigBoolParam("mads", "Mads"),
  ])


def lane_change_panel() -> SettingsPanel:
  return SettingsPanel([
    BigChoiceParam("lane change\nsmoothness", "LaneChangeSmoothing", LANE_CHANGE_SMOOTHING_CHOICES),
    BigChoiceParam("auto lane\nchange", "AutoLaneChangeTimer", LANE_CHANGE_CHOICES),
    BigBoolParam("delay with\nblind spot", "AutoLaneChangeBsmDelay"),
    BigChoiceParam("wait for\nlane width", "RoadEdgeMinLaneWidth", MIN_LANE_WIDTH_CHOICES, scale=0.1),
    BigBoolParam("block at\nroad edge", "RoadEdgeLaneChangeEnabled"),
  ])


def blinker_panel() -> SettingsPanel:
  return SettingsPanel([
    BigChoiceParam("pause steering\nwith blinker", "BlinkerPauseLateralControl", OFF_ON_CHOICES),
    BigChoiceParam("pause\nbelow", "BlinkerMinLateralControlSpeed", blinker_speed_choices(ui_state.is_metric)),
    BigChoiceParam("resume\ndelay", "BlinkerLateralReengageDelay", BLINKER_DELAY_CHOICES),
  ])


def screen_panel() -> SettingsPanel:
  return SettingsPanel([
    BigChoiceParam("menu\ntimeout", "InteractivityTimeout", TIMEOUT_CHOICES),
    BigChoiceParam("onroad\nbrightness", "OnroadScreenOffBrightness", ONROAD_BRIGHTNESS_CHOICES),
    BigBoolParam("screen saver", "ScreenSaverEnabled"),
    BigChoiceParam("screen saver\nduration", "ScreenSaverTimeout", SCREEN_SAVER_CHOICES),
  ])


def reset_today() -> None:
  """Forgets the stored daily distance, the next drive starts a new day. Only offroad, the car process is not running then."""
  ui_state.params.remove("DailyOdometer")


def driving_screen_panel() -> SettingsPanel:
  reset_btn = BigButton("reset\ntoday")
  reset_btn.set_click_callback(lambda: gui_app.push_widget(
    BigConfirmationDialog("slide to\nreset today", gui_app.texture("icons_mici/settings/device/reboot.png", 64, 70), reset_today)))
  reset_btn.set_enabled(lambda: ui_state.is_offroad())
  return SettingsPanel([
    BigBoolParam("gps speed", "ShowGpsSpeed"),
    BigBoolParam("lead\ndistance", "ShowLeadDistance"),
    BigBoolParam("brake dot", "ShowBrakeDot"),
    BigBoolParam("engine rpm", "ShowRpm"),
    reset_btn,
  ])


def lazy(make_panel: Callable[[], NavScroller]) -> Callable[[], None]:
  """Click handler that builds the panel the first time it is opened (the stock toggles page registers callbacks, so it
  must not be built again and again) and opens the same one afterwards. The panel refreshes its buttons when shown."""
  panels: list[NavScroller] = []

  def open_panel() -> None:
    if not panels:
      panels.append(make_panel())
    gui_app.push_widget(panels[0])

  return open_panel


class TogglesMenu(NavScroller):
  """The page behind 'toggles': the settings that matter on this car first, the stock toggles last in their own page."""

  def __init__(self):
    super().__init__()
    entries: list[tuple[str, str, Callable[[], NavScroller]]] = [
      ("hug", LKAS_ICON, hug_panel),
      ("steering", LKAS_ICON, steering_panel),
      ("lane change", ICON, lane_change_panel),
      ("blinker", ICON, blinker_panel),
      ("screen", ICON, screen_panel),
      ("driving\nscreen", ICON, driving_screen_panel),
      ("other\ntoggles", ICON, TogglesLayoutMici),
    ]
    buttons = []
    for title, icon, make_panel in entries:
      button = BigButton(title, "", gui_app.texture(icon, 64, 64))
      button.set_click_callback(lazy(make_panel))
      buttons.append(button)
    self._scroller.add_widgets(buttons)
