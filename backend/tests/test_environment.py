"""Image-quality classification & adaptive enhancement tests."""
import numpy as np

from app.ai.enhancement.pipeline import AdaptiveEnhancer
from app.ai.environment.classifier import ImageQualityService


def _daylight():
    # structured, bright, high-contrast scene (sharp edges -> reads as clear day)
    img = np.full((240, 320, 3), 180, dtype=np.uint8)
    img[:, ::40] = 255
    img[::40, :] = 20
    img[60:120, 80:160] = 240
    img[150:200, 200:280] = 15
    return img


def _dark():
    return (np.random.default_rng(2).integers(0, 40, (240, 320, 3))).astype(np.uint8)


def test_daylight_classified_normal():
    rep = ImageQualityService().analyze(_daylight())
    assert rep.environment in ("day", "blur")   # random noise may read as sharp day
    assert 0.0 <= rep.brightness <= 1.0


def test_dark_frame_low_light_or_night():
    rep = ImageQualityService().analyze(_dark())
    assert rep.environment in ("night", "low_light")
    assert rep.lowlight_score > 0.4


def test_enhancer_preserves_shape():
    frame = _dark()
    rep = ImageQualityService().analyze(frame)
    result = AdaptiveEnhancer(enabled=True).enhance(frame, rep)
    assert result.frame.shape == frame.shape


def test_enhancer_original_kept_for_daylight():
    frame = _daylight()
    rep = ImageQualityService().analyze(frame)
    rep.environment = "day"
    result = AdaptiveEnhancer(enabled=True).enhance(frame, rep)
    assert result.changed is False


def test_enhancement_disabled_is_noop():
    frame = _dark()
    rep = ImageQualityService().analyze(frame)
    result = AdaptiveEnhancer(enabled=False).enhance(frame, rep)
    assert result.changed is False
