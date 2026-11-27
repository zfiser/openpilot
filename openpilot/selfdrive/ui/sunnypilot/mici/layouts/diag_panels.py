"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Group panels of the car data page for the values read from the car's ECUs once a minute (carData items "diag_*", see the
Toyota diagnostic reader). One panel per group, each a full screen of the page: 12 V battery, tyres, hybrid battery,
drivetrain, climate. A panel shows only when the car reports at least one of its values; a value it does not have (or not
yet, or no longer) reads "--".
"""
from types import SimpleNamespace

PREFIX = "diag_"
OIL_KEY = "diag_oil_temp"  # on the driving screen, not on a panel
TYRES = (("fl", "Front left"), ("fr", "Front right"), ("rl", "Rear left"), ("rr", "Rear right"))
HV_TEMPS = tuple(f"diag_hv_temp{i}" for i in range(1, 7))
CHARGING_A = 0.5  # A, more into the 12 V battery is charging, more out of it is draining


def _value(items: dict, key: str):
  item = items.get(key)
  return float(item.value) if item is not None and item.valid else None


def _fmt(value, unit: str, decimals: int = 0) -> str:
  if value is None:
    return "--"
  return f"{value:,.{decimals}f} {unit}".strip()


def battery_12v_panel(items: dict):
  keys = ("diag_12v_v", "diag_12v_a", "diag_12v_temp", "diag_12v_smooth", "diag_12v_relay", "diag_aux_v", "diag_12v_km")
  if not any(k in items for k in keys):
    return None
  volts, amps = _value(items, "diag_12v_v"), _value(items, "diag_12v_a")
  state = None if amps is None else ("charging" if amps > CHARGING_A else "draining" if amps < -CHARGING_A else "idle")
  big = f"{_fmt(volts, 'V', 2)}   {'--' if amps is None else f'{amps:+.1f} A'}"
  return SimpleNamespace(key="panel_12v", title="12 V battery" + (f" - {state}" if state else ""), big=big, state=state, grid=None,
                         pairs=[("Temperature", _fmt(_value(items, "diag_12v_temp"), "°C", 1)),
                                ("Smoothed", _fmt(_value(items, "diag_12v_smooth"), "V", 2)),
                                ("Hybrid ECU", _fmt(_value(items, "diag_aux_v"), "V", 2)),
                                ("Before main relay", _fmt(_value(items, "diag_12v_relay"), "V", 2)),
                                ("Disconnected", _fmt(_value(items, "diag_12v_km"), "km ago"))])


def tyres_panel(items: dict):
  if not any(f"diag_tire_p_{w}" in items or f"diag_tire_t_{w}" in items for w, _ in TYRES):
    return None
  grid = [(name, _fmt(_value(items, f"diag_tire_p_{w}"), "kPa"), _fmt(_value(items, f"diag_tire_t_{w}"), "°C"))
          for w, name in TYRES]
  return SimpleNamespace(key="panel_tyres", title="Tyres", big=None, state=None, grid=grid, pairs=[])


def hybrid_battery_panel(items: dict):
  if not any(k in items for k in HV_TEMPS):
    return None
  temps = [_value(items, k) for k in HV_TEMPS]
  have = [t for t in temps if t is not None]
  big = f"{min(have):.1f} - {max(have):.1f} °C" if have else "--"
  return SimpleNamespace(key="panel_hv", title="Hybrid battery", big=big, state=None, grid=None,
                         pairs=[(f"Sensor {i}", _fmt(t, "°C", 1)) for i, t in enumerate(temps, 1)])


DRIVETRAIN = (("diag_coolant", "Coolant"), ("diag_transaxle_oil", "Transaxle oil"), ("diag_mg_inverter", "Motor inverter"),
              ("diag_gen_inverter", "Generator inverter"), ("diag_inverter_coolant", "Inverter coolant"),
              ("diag_rear_inverter_coolant", "Rear inv. coolant"))


def drivetrain_panel(items: dict):
  keys = [k for k, _ in DRIVETRAIN] + ["diag_boost_upper", "diag_boost_lower"]
  if not any(k in items for k in keys):
    return None
  up, low = _value(items, "diag_boost_upper"), _value(items, "diag_boost_lower")
  boost = "--" if up is None and low is None else f"{_fmt(up, '').strip() or '--'} / {_fmt(low, '°C')}"
  return SimpleNamespace(key="panel_drive", title="Drivetrain", big=None, state=None, grid=None,
                         pairs=[(label, _fmt(_value(items, k), "°C")) for k, label in DRIVETRAIN] + [("Boost converter", boost)])


def climate_panel(items: dict):
  keys = ("diag_cabin", "diag_ac_power")
  if not any(k in items for k in keys):
    return None
  return SimpleNamespace(key="panel_climate", title="Climate", big="Cabin " + _fmt(_value(items, "diag_cabin"), "°C", 1), state=None,
                         grid=None, pairs=[("A/C power", _fmt(_value(items, "diag_ac_power"), "kW", 1))])


PANELS = (battery_12v_panel, tyres_panel, hybrid_battery_panel, drivetrain_panel, climate_panel)


def build_panels(items: list) -> list:
  """The group panels for the diag_* items (any other item is ignored), in the fixed order, skipping empty groups."""
  by_key = {i.key: i for i in items if i.key.startswith(PREFIX)}
  panels = []
  for make in PANELS:
    try:
      panel = make(by_key)
    except Exception:
      panel = None
    if panel is not None:
      panels.append(panel)
  return panels


def oil_temp_text(items: list) -> str | None:
  """'92°' for the driving screen (drawn with a small thermometer in front), None without a reading."""
  for item in items:
    if item.key == OIL_KEY and item.valid:
      return f"{item.value:.0f}°"
  return None
