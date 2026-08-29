# Model Setup

```bash
python scripts/setup/download_models.py            # default yolov8n.pt
python scripts/setup/download_models.py yolov8s.pt # a larger model
```

The script:
- reports the Torch runtime (CPU/CUDA),
- ensures the YOLO weight exists (ultralytics downloads it to its cache if missing) and prints its size,
- checks EasyOCR availability (its recognition models, ~64 MB, download automatically on first OCR call),
- never pulls huge models silently — running this script is the explicit opt-in.

## Detector selection
`DETECTOR_BACKEND` chooses the backend; `auto` prefers YOLO, then torchvision SSDLite, then the
classical motion detector. All are real; the active one is shown in the UI and `/api/system/runtime`.

| Backend | Needs | Notes |
|---|---|---|
| `yolo` | `ultralytics` + weight | Best accuracy/speed; COCO vehicle classes |
| `torchvision` | `torch`/`torchvision` | SSDLite MobileNetV3, COCO pretrained |
| `motion` | OpenCV only | Background-subtraction; used for synthetic demo & as fallback |
| `null` | — | Reports unavailable (testing) |

## OCR engine selection
`OCR_ENGINE` = `easyocr` (default) | `tesseract` (needs the tesseract binary) | `paddleocr`.
`build_ocr_provider` falls back to any available engine and logs the substitution.

## Sizes (approx.)
- `yolov8n.pt` ≈ 6 MB · `yolov8s.pt` ≈ 22 MB
- EasyOCR English models ≈ 64 MB (first-use download)
- torchvision SSDLite weights ≈ 14 MB (first-use download)
