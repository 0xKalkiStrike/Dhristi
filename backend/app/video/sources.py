"""Video source abstraction.

    VideoSource
    ├── FileVideoSource
    ├── RTSPVideoSource
    └── WebcamVideoSource

The demo works fully in file mode; RTSP/webcam are supported when available and
degrade gracefully (no crash) when a source cannot be opened.
"""
from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from app.core.exceptions import VideoSourceError
from app.core.logging_config import get_logger

logger = get_logger("drishti.video")


@dataclass
class FrameData:
    ok: bool
    frame: Optional[np.ndarray]
    frame_id: int
    timestamp: float  # epoch seconds (source-relative for files)


class VideoSource(abc.ABC):
    kind = "base"
    is_live = False   # live sources (rtsp/webcam/bluetooth/browser) keep waiting on transient read failures

    def __init__(self, uri: str):
        self.uri = uri
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_id = 0
        self.fps = 25.0
        self.width = 0
        self.height = 0
        self._start_wall = time.time()

    @abc.abstractmethod
    def _open_target(self):
        ...

    def _make_capture(self, target):
        return cv2.VideoCapture(target)

    def open(self) -> None:
        target = self._open_target()
        cap = self._make_capture(target)
        if not cap.isOpened():
            raise VideoSourceError(f"cannot open {self.kind} source")
        self._cap = cap
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 25.0
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._start_wall = time.time()
        logger.info("video source opened", extra={"extra_fields": {
            "kind": self.kind, "fps": round(self.fps, 1), "w": self.width, "h": self.height}})

    def read(self) -> FrameData:
        if self._cap is None:
            return FrameData(False, None, self._frame_id, time.time())
        ok, frame = self._cap.read()
        if not ok:
            return FrameData(False, None, self._frame_id, self._timestamp())
        self._frame_id += 1
        return FrameData(True, frame, self._frame_id, self._timestamp())

    def _timestamp(self) -> float:
        # For files, derive a source-relative timestamp from frame index so speed
        # timing is independent of processing wall-clock.
        if self.kind == "file" and self.fps > 0:
            return self._frame_id / self.fps
        return time.time()

    @property
    def frame_count(self) -> int:
        if self._cap is None:
            return 0
        return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def seek(self, frame_index: int) -> None:
        if self._cap is not None:
            ok = self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            if ok:
                self._frame_id = frame_index
                return
        self.release()
        self.open()
        self._frame_id = 0

    def grab_frame(self, frame_index: int = 0) -> Optional[np.ndarray]:
        """One-shot frame grab (used for calibration preview)."""
        target = self._open_target()
        cap = cv2.VideoCapture(target)
        if not cap.isOpened():
            return None
        if frame_index:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        cap.release()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class FileVideoSource(VideoSource):
    kind = "file"

    def _open_target(self):
        import os
        if not os.path.exists(self.uri):
            raise VideoSourceError(f"video file not found: {self.uri}")
        return self.uri


class RTSPVideoSource(VideoSource):
    kind = "rtsp"
    is_live = True

    def __init__(self, uri: str):
        super().__init__(uri)
        self._thread: Optional[threading.Thread] = None
        self._latest_raw: Optional[np.ndarray] = None
        self._latest_ts: float = 0.0
        self._raw_seq: int = 0
        self._running = False
        self._lock = threading.Lock()
        self._new_frame_event = threading.Event()

    def _open_target(self):
        if not self.uri:
            raise VideoSourceError("RTSP URL not configured")
        uri = self.uri.strip()
        # If user entered http://ip:port or http://ip:port/ without a stream path,
        # auto-append /video (standard for IP Webcam apps)
        if uri.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            parsed = urlparse(uri)
            if not parsed.path or parsed.path == "/":
                uri = f"{uri.rstrip('/')}/video"
        return uri

    def open(self) -> None:
        super().open()
        if self._cap is not None:
            try:
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        self._running = True
        self._new_frame_event.clear()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True, name=f"rtsp-reader-{self.uri[:16]}")
        self._thread.start()

    def _reader_loop(self) -> None:
        """Continuously grab newest frame to completely eliminate stream buffering lag."""
        while self._running and self._cap is not None and self._cap.isOpened():
            ok, frame = self._cap.read()
            if ok and frame is not None:
                # Resize if ultra-high resolution (e.g. 1080p -> 720p) to ensure smooth 15-25 FPS on CPU
                h, w = frame.shape[:2]
                if w > 640 or h > 480:
                    scale = min(640.0 / w, 480.0 / h)
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
                with self._lock:
                    self._latest_raw = frame
                    self._latest_ts = time.time()
                    self._raw_seq += 1
                self._new_frame_event.set()
            else:
                time.sleep(0.01)

    def read(self) -> FrameData:
        self._new_frame_event.wait(timeout=0.04)
        with self._lock:
            frame = self._latest_raw
            ts = self._latest_ts
            seq = self._raw_seq
            self._new_frame_event.clear()
        if frame is None:
            return FrameData(False, None, self._frame_id, time.time())
        self._frame_id = seq
        return FrameData(True, frame, self._frame_id, ts or time.time())

    def release(self) -> None:
        self._running = False
        self._new_frame_event.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None
        super().release()


def _open_local_camera(index: int):
    """Open a local OS video device, prioritizing DirectShow on Windows for instant initialization."""
    import sys
    backends = [cv2.CAP_DSHOW] if sys.platform.startswith("win") else [cv2.CAP_ANY]
    for be in backends:
        try:
            cap = cv2.VideoCapture(index, be)
            if cap.isOpened():
                try:
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
                return cap
            cap.release()
        except Exception:
            pass
    return cv2.VideoCapture(index)


class LiveDeviceVideoSource(VideoSource):
    """Base class for live device sources (Webcam, USB, Bluetooth cameras) with zero-lag reading."""
    is_live = True

    def __init__(self, uri: str):
        super().__init__(uri)
        self._thread: Optional[threading.Thread] = None
        self._latest_raw: Optional[np.ndarray] = None
        self._latest_ts: float = 0.0
        self._raw_seq: int = 0
        self._running = False
        self._lock = threading.Lock()
        self._new_frame_event = threading.Event()

    def open(self) -> None:
        super().open()
        if self._cap is not None:
            try:
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        self._running = True
        self._new_frame_event.clear()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True, name=f"cam-reader-{self.uri}")
        self._thread.start()

    def _reader_loop(self) -> None:
        """Continuously grab the latest frame to completely eliminate DirectShow / MSMF queue lag."""
        while self._running and self._cap is not None and self._cap.isOpened():
            ok, frame = self._cap.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                if w > 640 or h > 480:
                    scale = min(640.0 / w, 480.0 / h)
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
                with self._lock:
                    self._latest_raw = frame
                    self._latest_ts = time.time()
                    self._raw_seq += 1
                self._new_frame_event.set()
            else:
                time.sleep(0.005)

    def read(self) -> FrameData:
        self._new_frame_event.wait(timeout=0.04)
        with self._lock:
            frame = self._latest_raw
            ts = self._latest_ts
            seq = self._raw_seq
            self._new_frame_event.clear()
        if frame is None:
            return FrameData(False, None, self._frame_id, time.time())
        self._frame_id = seq
        return FrameData(True, frame, self._frame_id, ts or time.time())

    def release(self) -> None:
        self._running = False
        self._new_frame_event.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None
        super().release()


class WebcamVideoSource(LiveDeviceVideoSource):
    kind = "webcam"

    def _open_target(self):
        try:
            return int(self.uri)
        except (TypeError, ValueError):
            return 0

    def _make_capture(self, target):
        return _open_local_camera(int(target))


class BluetoothVideoSource(LiveDeviceVideoSource):
    """A Bluetooth camera exposed by the OS as a standard video device.

    Note: Bluetooth (BLE/Classic) cannot carry real-time video by itself. A
    Bluetooth camera must be **paired in the OS first**, after which the OS
    presents it as a normal camera/video device; we then open it by its device
    index just like a webcam. ``source_uri`` is that device index.
    """
    kind = "bluetooth"

    def _open_target(self):
        try:
            return int(self.uri)
        except (TypeError, ValueError):
            return 0

    def _make_capture(self, target):
        return _open_local_camera(int(target))


def build_video_source(source_type: str, uri: str) -> VideoSource:
    st = (source_type or "file").lower()
    if st == "rtsp":
        return RTSPVideoSource(uri)
    if st == "webcam":
        return WebcamVideoSource(uri)
    if st == "bluetooth":
        return BluetoothVideoSource(uri)
    if st in ("browser", "push"):
        from app.video.push import PushVideoSource
        return PushVideoSource(uri)
    return FileVideoSource(uri)
