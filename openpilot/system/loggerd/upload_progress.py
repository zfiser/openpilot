"""Upload progress shared with the UI through small files in RAM (/dev/shm), one per uploading process.

Each writer (uploader, sunnylink uploader, athenad) keeps its own file, so no two processes write the same one. A file holds
{"active": bool, "done": bytes, "total": bytes, "t": monotonic time (shared by all processes)}. The UI adds the sources up and draws a line on the home screen.
Nothing here may raise: a failure only means the line is not drawn.
"""
import json
import os
import time

PROGRESS_DIR = "/dev/shm"
PREFIX = "upload_progress_"
WRITE_INTERVAL = 0.5  # s, at most two writes a second while a file is sent
STALE_AFTER = 30.0  # s, a writer that stopped updating (crash, kill) counts as idle


def progress_path(source: str) -> str:
  return os.path.join(PROGRESS_DIR, f"{PREFIX}{source}.json")


class UploadProgressWriter:
  def __init__(self, source: str):
    self.path = progress_path(source)
    self._last_write = 0.0
    self._last: tuple[bool, int, int] | None = None

  def update(self, done: int, total: int, force: bool = False) -> None:
    self._write(True, done, total, force)

  def idle(self) -> None:
    self._write(False, 0, 0, True)

  def _write(self, active: bool, done: int, total: int, force: bool) -> None:
    try:
      now = time.monotonic()
      state = (active, int(done), int(total))
      if state == self._last and now - self._last_write < STALE_AFTER / 3:
        return  # unchanged, only refresh now and then so the reader does not see it as stale
      if not force and now - self._last_write < WRITE_INTERVAL:
        return
      if not active and self._last is not None and not self._last[0]:
        return  # already idle
      tmp = self.path + ".tmp"
      with open(tmp, "w") as f:
        json.dump({"active": active, "done": state[1], "total": state[2], "t": time.monotonic()}, f)
      os.replace(tmp, self.path)
      self._last, self._last_write = state, now
    except Exception:
      pass


def read_progress(now: float | None = None) -> tuple[bool, float]:
  """(uploading, fraction 0..1) over all sources. Never raises."""
  done = total = 0
  active = False
  try:
    now = time.monotonic() if now is None else now
    for name in os.listdir(PROGRESS_DIR):
      if not (name.startswith(PREFIX) and name.endswith(".json")):
        continue
      try:
        with open(os.path.join(PROGRESS_DIR, name)) as f:
          d = json.load(f)
        if not d.get("active") or now - float(d.get("t", 0)) > STALE_AFTER:
          continue
        active = True
        done += max(0, int(d.get("done", 0)))
        total += max(0, int(d.get("total", 0)))
      except Exception:
        continue
  except Exception:
    return False, 0.0
  if not active:
    return False, 0.0
  return True, (min(1.0, done / total) if total > 0 else 0.0)
