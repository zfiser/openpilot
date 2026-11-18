"""fork: with the CellularModem setting off (modem.py state OFF) the eSIM profiles are not polled."""
from unittest import mock

import openpilot.system.ui.lib.cellular_manager as cm_mod


def tick(cm, state: dict):
  cm._last_profile_poll = 0.0  # the poll interval has passed
  with mock.patch.object(cm_mod.HARDWARE, "get_modem_state", return_value=state), \
       mock.patch.object(cm, "_poll_profiles") as poll:
    cm.process_callbacks()
  return poll.called


class TestModemOff:
  def test_no_polling_while_off_and_again_when_on(self):
    cm = cm_mod.CellularManager()
    assert not tick(cm, {"state": "OFF"})
    assert cm.modem_off
    assert tick(cm, {"state": "INITIALIZING"})
    assert not cm.modem_off
    assert tick(cm, {})  # no state file (other devices, modem.py not running): as before
