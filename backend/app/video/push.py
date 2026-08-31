"""Push-based (browser) camera frames.

A phone/laptop browser captures its own camera (via getUserMedia) and pushes JPEG
frames to the backend, which analyses them through the normal pipeline. Frames are
delivered here keyed by camera_id; ``PushVideoSource`` reads the latest frame so
the pipeline runs on live browser input (no demo data).
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from app.video.sources import FrameData, VideoSource


class _Holder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._ts = 0.0
        self._seq = 0
        self._event = threading.Event()

    def push(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame
            self._ts = time.time()
            self._seq += 1
        self._event.set()

    def get(self, timeout: float):
        if self._event.wait(timeout):
            with self._lock:
                self._event.clear()
                return self._frame, self._ts
        with self._lock:
            return self._frame, self._ts


_holders: dict[str, _Holder] = {}
_holders_lock = threading.Lock()


def _get_holder(camera_id: str) -> _Holder:
    with _holders_lock:
        h = _holders.get(camera_id)
        if h is None:
            h = _Holder()
            _holders[camera_id] = h
        return h


def push_frame(camera_id: str, frame: np.ndarray) -> None:
    _get_holder(camera_id).push(frame)


def drop_holder(camera_id: str) -> None:
    with _holders_lock:
        _holders.pop(camera_id, None)


class PushVideoSource(VideoSource):
    """Reads frames pushed by a browser instead of pulling from a device/file."""

    kind = "browser"
    is_live = True

    def _open_target(self):
        return self.uri  # camera_id is the holder key

    def open(self) -> None:
        from app.core.config import settings
        self._holder = _get_holder(self.uri)
        self.fps = float(settings.process_fps)
        self.width = 0
        self.height = 0
        self._frame_id = 0

    def read(self) -> FrameData:
        holder = getattr(self, "_holder", None)
        if holder is None:
            return FrameData(False, None, self._frame_id, time.time())
        frame, ts = holder.get(0.5)
        if frame is None:
            return FrameData(False, None, self._frame_id, time.time())  # idle; pipeline waits
        self._frame_id += 1
        if not self.width:
            self.height, self.width = frame.shape[:2]
        return FrameData(True, frame, self._frame_id, ts)

    def release(self) -> None:
        drop_holder(self.uri)
