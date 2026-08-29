"""Central configuration for DRISHTI-V backend.

All tunable behaviour is driven from environment variables (see ``.env.example``)
so nothing operationally sensitive is hard-coded. Values have safe, runnable
defaults so the stack works out-of-the-box for the hackathon demo.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository roots (…/backend/app/core/config.py -> repo root)
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
CONFIG_DIR = REPO_ROOT / "configs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "DRISHTI-V"
    app_subtitle: str = "Dynamic Road Intelligence & Surveillance Through Intelligent Vision"
    version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # ---- Database ----
    # Default to a local SQLite file so the platform runs with zero external
    # services. Set DATABASE_URL to a PostgreSQL DSN for the full stack, e.g.
    # postgresql+psycopg://user:pass@localhost:5432/drishti
    database_url: str = Field(default=f"sqlite:///{(DATA_DIR / 'drishti.db').as_posix()}")

    # ---- CORS ----
    # NoDecode: accept a plain comma-separated string from .env (the validator
    # splits it) instead of requiring a JSON array.
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Allow any private-LAN origin (so phones/laptops on the same Wi-Fi can use
    # the app when accessing the backend/forwarder directly).
    cors_allow_lan: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # ---- AI runtime ----
    ai_device: str = "auto"            # auto|cpu|cuda
    detector_backend: str = "auto"     # auto|yolo|torchvision|motion|null
    yolo_model: str = "yolov8n.pt"     # ultralytics weight name / path
    detection_confidence: float = 0.35
    detection_iou: float = 0.5
    # Frame sampling: run the expensive detector every N processed frames;
    # cheap tracker/interpolation fills the gaps.
    detect_every_n_frames: int = 5
    process_fps: float = 25.0          # target processing FPS (smooth real-time playback)

    # ---- Tracking ----
    track_high_thresh: float = 0.5
    track_low_thresh: float = 0.2
    track_max_age: int = 30            # frames to keep a lost track alive
    track_min_hits: int = 3
    track_iou_match: float = 0.3

    # ---- OCR / ANPR ----
    ocr_engine: str = "easyocr"        # easyocr|tesseract|paddleocr
    ocr_min_confidence: float = 0.4
    anpr_min_plate_area: int = 400     # px^2 minimum candidate plate area
    anpr_verify_confidence: float = 0.75  # below this -> "needs verification"
    plate_country: str = "IN"

    # ---- Enhancement / environment ----
    enhancement_enabled: bool = True
    fog_score_threshold: float = 0.45
    lowlight_score_threshold: float = 0.40
    blur_score_threshold: float = 100.0   # variance-of-laplacian below -> blur

    # ---- Speed ----
    default_speed_limit_kmh: float = 60.0
    speed_min_confidence: float = 0.5

    # ---- MongoDB (native, non-Docker; used as a live event/analytics store) ----
    mongodb_enabled: bool = True
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "drishti_v"
    mongodb_events_collection: str = "live_events"
    mongodb_timeout_ms: int = 1500

    # ---- Uploads ----
    max_upload_mb: int = 500
    allowed_video_ext: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    )

    @field_validator("allowed_video_ext", mode="before")
    @classmethod
    def _split_ext(cls, v):
        if isinstance(v, str):
            return [e.strip() for e in v.split(",") if e.strip()]
        return v

    # ---- Security ----
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 720
    data_retention_days: int = 90

    # ---- Paths ----
    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    @property
    def config_dir(self) -> Path:
        return CONFIG_DIR

    @property
    def sample_videos_dir(self) -> Path:
        return DATA_DIR / "sample_videos"

    @property
    def outputs_dir(self) -> Path:
        return DATA_DIR / "outputs"

    @property
    def models_dir(self) -> Path:
        return DATA_DIR / "models"

    def ensure_dirs(self) -> None:
        for p in [
            self.data_dir,
            self.sample_videos_dir,
            self.outputs_dir,
            self.outputs_dir / "plates",
            self.outputs_dir / "frames",
            self.models_dir,
            DATA_DIR / "demo_images",
        ]:
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
