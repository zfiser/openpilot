from openpilot.selfdrive.ui.sunnypilot.mici.layouts.upload_status import status_text


def test_idle():
  assert status_text(False, 0, 0, None, None) == ("uploads", "nothing to send")


def test_starting_shows_size_left():
  assert status_text(True, 0, 270_000_000, None, None) == ("uploading 0%", "270 MB left")


def test_running():
  assert status_text(True, 45, 100, 1_200_000, 185) == ("uploading 45%", "1.2 MB/s, 3 min")


def test_stalled():
  assert status_text(True, 45, 100, 0.0, None) == ("uploading 45%", "stalled")
