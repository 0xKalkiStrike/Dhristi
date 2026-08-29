"""OCR provider abstraction.

    OCRProvider
    ├── EasyOCRProvider
    ├── TesseractProvider
    └── PaddleOCRProvider
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

import numpy as np


@dataclass
class OCRResult:
    text: str
    confidence: float
    engine: str


class OCRProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def read_text(self, image: np.ndarray) -> OCRResult:
        """Run OCR on a (preprocessed) plate crop and return best text + confidence."""

    @property
    def available(self) -> bool:
        return True
