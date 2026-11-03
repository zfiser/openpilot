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
