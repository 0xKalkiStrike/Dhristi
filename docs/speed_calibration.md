# Speed Calibration & Estimation

Speed is derived from **calibrated scene geometry**, never from raw pixel motion.

## Method A — Dual virtual lines (default)

Two lines are drawn on the road image a **known real-world distance** apart (e.g. 24 m).
As a tracked vehicle's centre crosses line A then line B, the crossing times are recorded
(using **source-relative timestamps**, so timing is independent of processing FPS).

```
elapsed  = |t_B − t_A|
speed_ms = real_distance_m / elapsed
speed_kmh = speed_ms × 3.6
```

Confidence is high (~0.94) for clean crossings and reduced when the elapsed interval is
implausibly short (unreliable timing).

## Method B — Homography

Four image points are mapped to four world points (metres) via `cv2.findHomography`.
Each trajectory sample is projected to the ground plane; instantaneous speeds are computed
between consecutive metric positions, and the **median** is reported (robust to jitter).
Confidence scales inversely with the coefficient of variation of the samples.

## Calibration UI (`/calibration`)

1. Select a camera → a frame loads.
2. Click 2 points for **Line A** (cyan) and 2 for **Line B** (amber).
3. Enter the real distance (m), speed limit (km/h), and allowed direction.
4. **Save** → **Test** runs a synthetic crossing and shows the estimated speed.

Calibration is stored in `camera_calibrations` and used live by the pipeline.

## Worked example

```
Reference distance : 25.0 m
Timestamp A        : 18:42:11.200
Timestamp B        : 18:42:12.020
Elapsed            : 0.820 s
Estimated speed    : 25.0 / 0.820 × 3.6 = 109.76 km/h
Configured limit   : 80 km/h
Excess             : 29.76 km/h
Confidence         : 94%
```

## Guarantees & guards

- Zero or negative elapsed time → raises `SpeedComputationError` (no divide-by-zero).
- Negative distance → rejected.
- No / invalid calibration → estimator reports **unavailable**; the UI shows
  *“Speed estimation unavailable — camera calibration required.”*
- Every result is labelled **Estimated** and carries a confidence score.

## Accuracy caveats

Precision depends on camera perspective, lens distortion, frame rate, and how accurately the
real-world distance was measured. Treat values as estimates requiring human verification for
enforcement decisions.
