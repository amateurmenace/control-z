"""The suite's frame service: server-side decode → cached JPEGs at viewer size.

Design (specs/08 §2): PyAV decodes, the browser only ever sees JPEG — no
in-browser codec fights. Frames are cached per (file, mtime, height) so a
second scrub is instant; a small prefetcher warms the frames around the
playhead. Frame indices are derived from pts (frame-accurate on CFR sources;
VFR is out of scope for v0.1 and probed footage reports it).
"""

from __future__ import annotations

import hashlib
import threading
from fractions import Fraction
from pathlib import Path
from typing import Optional, Tuple


def cache_root() -> Path:
    d = Path.home() / "Library" / "Caches" / "control-z" / "suite" / "frames"
    d.mkdir(parents=True, exist_ok=True)
    return d


def clip_cache_dir(path: str, height: int) -> Path:
    p = Path(path)
    tag = hashlib.md5(f"{p.resolve()}:{p.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    d = cache_root() / tag / f"h{height}"
    d.mkdir(parents=True, exist_ok=True)
    return d


class _Reader:
    """One open container, decoding forward; seeks only when it must."""

    def __init__(self, path: str):
        import av

        self.path = path
        self.container = av.open(path)
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"
        rate = self.stream.average_rate or Fraction(24, 1)
        self.fps = float(rate)
        self.next_index = 0          # index the decoder will produce next
        self._iter = self.container.decode(self.stream)

    def _frame_index(self, frame) -> int:
        if frame.pts is None:
            return max(self.next_index, 0)
        t = float(frame.pts * (self.stream.time_base or Fraction(1, 90000)))
        return int(round(t * self.fps))

    def read(self, index: int, on_pass=None):
        """Decode and return frame `index`. Frames passed on the way to a
        seek target stream through on_pass(i, frame) — never accumulated
        (a long-GOP seek can pass a whole GOP of 4K frames)."""
        if index < self.next_index or index > self.next_index + 48:
            # backward or far forward: seek to the keyframe before the target
            ts = int(index / self.fps / (self.stream.time_base or Fraction(1, 90000)))
            self.container.seek(ts, stream=self.stream, backward=True)
            self._iter = self.container.decode(self.stream)
            self.next_index = -1  # unknown until the first decoded pts
        for frame in self._iter:
            i = self._frame_index(frame)
            self.next_index = i + 1
            if i < index:
                if on_pass:
                    on_pass(i, frame)
                continue
            return frame, i
        return None, -1  # EOF

    def close(self):
        try:
            self.container.close()
        except Exception:
            pass


class FrameService:
    def __init__(self, prefetch: int = 12, max_readers: int = 2):
        self.prefetch_n = prefetch
        self.max_readers = max_readers
        self._readers: dict = {}
        self._order: list = []
        self._lock = threading.Lock()
        self._want = None           # latest prefetch request wins
        self._wake = threading.Event()
        t = threading.Thread(target=self._prefetch_loop, daemon=True)
        t.start()

    # -- public ---------------------------------------------------------------

    def frame_path(self, path: str, index: int, height: int = 540,
                   prefetch: bool = True) -> Optional[Path]:
        """Path to the cached JPEG for (clip, frame, height); decodes on miss."""
        f = clip_cache_dir(path, height) / f"f_{index:05d}.jpg"
        if not f.exists():
            ok = self._decode_into_cache(path, index, height)
            if not ok:
                return None
        if prefetch:
            self._want = (path, index + 1, height)
            self._wake.set()
        return f if f.exists() else None

    def probe_fps(self, path: str) -> float:
        with self._lock:
            return self._reader(path).fps

    def native_frame(self, path: str, index: int):
        """Full-resolution BGR ndarray of one frame (Rise's loupe/preview path).
        Not cached — native 4K frames are too big to keep as JPEGs."""
        with self._lock:
            frame, got = self._reader(path).read(index)
            if frame is None:
                return None
            return frame.to_ndarray(format="bgr24")

    def close_all(self):
        with self._lock:
            for r in self._readers.values():
                r.close()
            self._readers.clear()
            self._order.clear()

    # -- internals --------------------------------------------------------------

    def _reader(self, path: str) -> _Reader:
        """Callers hold self._lock."""
        if path not in self._readers:
            if len(self._order) >= self.max_readers:
                old = self._order.pop(0)
                self._readers.pop(old).close()
            self._readers[path] = _Reader(path)
            self._order.append(path)
        else:
            self._order.remove(path)
            self._order.append(path)
        return self._readers[path]

    def _write_jpeg(self, frame, path: str, index: int, height: int):
        import cv2

        img = frame.to_ndarray(format="bgr24")
        h, w = img.shape[:2]
        if h > height:
            nw = max(2, int(round(w * height / h / 2)) * 2)
            img = cv2.resize(img, (nw, height), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 87])
        if not ok:
            return
        out = clip_cache_dir(path, height) / f"f_{index:05d}.jpg"
        tmp = out.with_suffix(".part")
        tmp.write_bytes(buf.tobytes())
        tmp.rename(out)

    def _decode_into_cache(self, path: str, index: int, height: int) -> bool:
        with self._lock:
            try:
                reader = self._reader(path)
                frame, got = reader.read(
                    index,
                    on_pass=lambda i, f: self._write_jpeg(f, path, i, height))
            except Exception:
                # a broken reader must not wedge the service — drop it
                r = self._readers.pop(path, None)
                if r:
                    self._order.remove(path)
                    r.close()
                return False
            if frame is not None:
                self._write_jpeg(frame, path, got, height)
        if frame is None:
            return False
        if got != index:
            # CFR mismatch (or EOF short) — serve what the pts math says this is;
            # honesty: don't alias another frame under the asked-for index
            return (clip_cache_dir(path, height) / f"f_{index:05d}.jpg").exists()
        return True

    def _prefetch_loop(self):
        while True:
            self._wake.wait()
            self._wake.clear()
            want = self._want
            if not want:
                continue
            path, start, height = want
            for i in range(start, start + self.prefetch_n):
                if self._want != want:  # a newer request superseded this one
                    break
                f = clip_cache_dir(path, height) / f"f_{i:05d}.jpg"
                if f.exists():
                    continue
                if not self._decode_into_cache(path, i, height):
                    break
