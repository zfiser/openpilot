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


def read_totals(now: float | None = None) -> tuple[bool, int, int]:
  """(uploading, bytes done, bytes in total) over all sources. Never raises."""
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
    return False, 0, 0
  return active, (done if active else 0), (total if active else 0)


def read_progress(now: float | None = None) -> tuple[bool, float]:
  """(uploading, fraction 0..1) over all sources. Never raises."""
  active, done, total = read_totals(now)
  if not active:
    return False, 0.0
  return True, (min(1.0, done / total) if total > 0 else 0.0)


class UploadRate:
  """Upload speed over the last WINDOW seconds and the time left at that speed. Feed it read_totals() about once a second."""
  WINDOW = 10.0  # s
  MIN_SPAN = 2.0  # s of samples before a speed is shown

  def __init__(self):
    self._samples: list[tuple[float, int]] = []

  def update(self, now: float, active: bool, done: int, total: int) -> tuple[float | None, float | None]:
    """(bytes per second or None while unknown, seconds left or None)."""
    if not active:
      self._samples.clear()
      return None, None
    if self._samples and done < self._samples[-1][1]:
      self._samples.clear()  # a new run of uploads started from zero
    self._samples.append((now, done))
    while len(self._samples) > 2 and now - self._samples[0][0] > self.WINDOW:
      self._samples.pop(0)
    t0, d0 = self._samples[0]
    if now - t0 < self.MIN_SPAN:
      return None, None
    speed = (done - d0) / (now - t0)
    if speed <= 0:
      return 0.0, None
    return speed, max(0, total - done) / speed


def format_bytes(n: float) -> str:
  if n >= 1e9:
    return f"{n / 1e9:.1f} GB"
  if n >= 1e6:
    return f"{n / 1e6:.0f} MB" if n >= 1e8 else f"{n / 1e6:.1f} MB"
  return f"{n / 1e3:.0f} kB"


def format_speed(bps: float) -> str:
  return format_bytes(bps) + "/s"


def format_duration(seconds: float) -> str:
  s = int(round(seconds))
  if s < 60:
    return f"{s} s"
  m = (s + 30) // 60
  if m < 60:
    return f"{m} min"
  return f"{m // 60} h {m % 60} min"
