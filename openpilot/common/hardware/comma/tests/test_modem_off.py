"""fork: the CellularModem setting in modem.py (off = the modem is powered down and left alone)."""
from unittest import mock

import openpilot.common.hardware.comma.modem as modem


def make(params: dict, at_port: bool = True):
  m = modem.Modem()
  m._read_param = lambda key: params.get(key, "")
  m._ppp = mock.MagicMock()
  m._publish_state = mock.MagicMock()
  return m


def lte_calls(run):
  return [c.args[0][2] for c in run.call_args_list if c.args and c.args[0][:2] == ["sudo", modem.LTE_SCRIPT]]


class TestModemOff:
  def test_on_unless_explicitly_off(self):
    assert make({})._modem_wanted()
    assert make({"CellularModem": "1"})._modem_wanted()
    assert not make({"CellularModem": "0"})._modem_wanted()

  def test_power_off_never_raises(self):
    m = make({"CellularModem": "0"})
    m._ppp.kill.side_effect = RuntimeError("boom")
    with mock.patch.object(modem.subprocess, "run", side_effect=OSError("no sudo")) as run:
      m._power_off()
    assert run.called
    m._publish_state.assert_called_with(state="OFF")

  def test_off_repowers_down_only_after_the_retry_time(self):
    m = make({"CellularModem": "0"})
    with mock.patch.object(modem.subprocess, "run") as run, mock.patch.object(modem.os.path, "exists", return_value=True), \
         mock.patch.object(modem.time, "monotonic", side_effect=[100.0, 110.0, 140.0, 140.0]):
      m._power_off()  # at 100 s
      assert m._do_off() == modem.State.OFF  # 110 s: the modem is still going down, no second pulse
      assert m._do_off() == modem.State.OFF  # 140 s: still there (e.g. the eSIM screen started it), down again
    assert lte_calls(run) == ["stop", "stop"]

  def test_run_switches_off_and_back_on(self):
    params = {"CellularModem": "0"}
    m = make(params)
    steps = []

    def sleep(_):
      steps.append(1)
      if len(steps) == 2:
        params["CellularModem"] = "1"  # the user turns it back on
      if len(steps) == 3:
        m.running = False

    m._do_initializing = mock.MagicMock(return_value=modem.State.INITIALIZING)
    m._check_iccid = mock.MagicMock()
    with mock.patch.object(modem.subprocess, "run") as run, mock.patch.object(modem.time, "sleep", side_effect=sleep), \
         mock.patch.object(modem.os.path, "exists", return_value=False), \
         mock.patch.object(modem.Modem, "_has_modem_manager", return_value=False):
      m.run()
    assert lte_calls(run) == ["stop", "start"]
    assert m._do_initializing.called  # the normal start sequence after switching back on
