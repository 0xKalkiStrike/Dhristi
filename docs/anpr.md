# ANPR / Number-Plate Recognition

## Pipeline

```
vehicle crop
  → PlateDetector.detect()        # classical: Sobel edges + morphology + aspect-ratio filter
  → preprocess_for_ocr()          # upscale + bilateral filter + adaptive threshold
  → OCRProvider.read_text()       # EasyOCR (default) | Tesseract | PaddleOCR
  → normalize_plate()             # clean, uppercase, position-aware confusion fixes
  → validate                      # Indian standard + BH-series patterns
  → combined confidence           # OCR score × format factor
```

No dedicated deep plate-detector ships in this environment, so candidate plate regions are
found with **classical CV** (explainable, fast). When a real plate-detection model is added,
it drops into `PlateDetector` without touching the rest of the pipeline.

## OCR abstraction

```
OCRProvider
├── EasyOCRProvider     (default; installed)
├── TesseractProvider   (needs the tesseract binary)
└── PaddleOCRProvider   (optional)
```
`build_ocr_provider(OCR_ENGINE)` picks the requested engine, falling back to any available one.

## Normalisation (India)

- Strip non-alphanumerics, uppercase.
- **Position-aware** confusion resolution only where the plate grammar is unambiguous
  (e.g. `O→0` in a digit slot, `8→B` in a letter slot). OCR output is never blindly rewritten.
- Validated against:
  - Standard: `^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$` (e.g. `GJ01AB1234`)
  - BH-series: `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$` (e.g. `22BH1234AA`)

## Storage & verification

Each read stores **raw text, normalised text, confidence, engine, plate bbox, crop path,
timestamp, camera, tracking id**. Reads below `ANPR_VERIFY_CONFIDENCE` (0.75) or with an
invalid format are flagged **Needs Verification** in the UI. The vehicle identity keeps the
highest-confidence plate; low-confidence reads never silently overwrite a good one.

## Limitations

Accuracy depends on plate resolution, motion blur, lighting and occlusion. When no legible
plate is present the pipeline returns nothing (it never fabricates a plate). If sample input
lacks readable plates, the UI shows an *ANPR data unavailable* state.
