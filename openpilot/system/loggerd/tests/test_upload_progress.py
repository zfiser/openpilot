import json
import time

from openpilot.system.loggerd import upload_progress as up


def _setup(tmp_path, monkeypatch):
  monkeypatch.setattr(up, "PROGRESS_DIR", str(tmp_path))


def test_idle_when_nothing_written(tmp_path, monkeypatch):
  _setup(tmp_path, monkeypatch)
  assert up.read_progress() == (False, 0.0)


def test_sources_add_up(tmp_path, monkeypatch):
  _setup(tmp_path, monkeypatch)
  up.UploadProgressWriter("a").update(25, 100, force=True)
  up.UploadProgressWriter("b").update(25, 100, force=True)
  assert up.read_progress() == (True, 0.25)


def test_idle_source_ignored(tmp_path, monkeypatch):
  _setup(tmp_path, monkeypatch)
  w = up.UploadProgressWriter("a")
  w.update(10, 100, force=True)
  w.idle()
  up.UploadProgressWriter("b").update(50, 100, force=True)
  assert up.read_progress() == (True, 0.5)


def test_stale_source_ignored(tmp_path, monkeypatch):
  _setup(tmp_path, monkeypatch)
  up.UploadProgressWriter("a").update(10, 100, force=True)
  assert up.read_progress(now=time.monotonic() + up.STALE_AFTER + 1) == (False, 0.0)


def test_writes_throttled(tmp_path, monkeypatch):
  _setup(tmp_path, monkeypatch)
  w = up.UploadProgressWriter("a")
  w.update(10, 100, force=True)
  w.update(20, 100)  # within WRITE_INTERVAL, skipped
  with open(up.progress_path("a")) as f:
    assert json.load(f)["done"] == 10


def test_broken_file_and_missing_dir_never_raise(tmp_path, monkeypatch):
  _setup(tmp_path, monkeypatch)
  (tmp_path / "upload_progress_x.json").write_text("{not json")
  assert up.read_progress() == (False, 0.0)
  monkeypatch.setattr(up, "PROGRESS_DIR", str(tmp_path / "missing"))
  up.UploadProgressWriter("a").update(1, 2, force=True)  # write fails silently
  assert up.read_progress() == (False, 0.0)


def test_rate_needs_a_few_seconds():
  r = up.UploadRate()
  assert r.update(0.0, True, 0, 1000) == (None, None)
  assert r.update(1.0, True, 100, 1000) == (None, None)
  speed, eta = r.update(2.0, True, 200, 1000)
  assert speed == 100 and eta == 8


def test_rate_window_and_reset():
  r = up.UploadRate()
  for t in range(30):
    r.update(float(t), True, t * 50, 10_000)
  speed, _ = r.update(30.0, True, 2000, 10_000)  # faster lately: only the last 10 s count (1000 -> 2000 bytes)
  assert speed == 100
  assert r.update(31.0, True, 10, 500) == (None, None)  # new batch started over
  assert r.update(32.0, False, 0, 0) == (None, None)


def test_rate_stalled():
  r = up.UploadRate()
  r.update(0.0, True, 100, 1000)
  assert r.update(5.0, True, 100, 1000) == (0.0, None)


def test_formatting():
  assert up.format_speed(1_234_000) == "1.2 MB/s"
  assert up.format_speed(350_000) == "350 kB/s"
  assert up.format_bytes(270_000_000) == "270 MB"
  assert up.format_duration(45) == "45 s"
  assert up.format_duration(185) == "3 min"
  assert up.format_duration(4800) == "1 h 20 min"
