# Limitations & Honest Disclosures

DRISHTI-V is a confidence-aware system with graceful degradation. It does **not** claim 100 %
accuracy or zero bugs. Known limitations:

## Speed
- Requires **camera calibration**; without it, speed is not reported (the UI says so).
- Accuracy depends on camera perspective, lens distortion, frame rate, and how precisely the
  real-world reference distance was measured. Results are labelled **Estimated**.
- Uncalibrated CCTV cannot provide exact physical speed — treat outputs as estimates needing
  human verification for enforcement.

## Detection
- Severe fog, heavy rain, extreme low light, or strong motion blur reduce accuracy.
- On synthetic demo scenes, the classical **motion detector** is used (abstract blobs are not
  COCO objects). Real footage uses YOLO. The active detector is always shown in the UI.
- CPU-only machines run at reduced FPS (configurable).

## ANPR / OCR
- Depends on plate resolution, angle, lighting and blur. Small or distant plates may read
  partially or not at all — such reads are flagged **Needs Verification** and never fabricated.
- Normalisation is India-focused (standard + BH series); other formats validate as "unknown".
- The classical plate-region detector can miss/segment plates imperfectly; a deep plate model
  can be dropped into the `PlateDetector` interface to improve this.

## Cross-camera identity
- Association is **probabilistic**, combining plate, appearance (colour histogram), class and
  time. It can miss or mis-associate; every association carries a confidence score.
- Appearance colour on very small/low-light vehicles can vary between observations.

## General
- Synthetic demo data is for demonstration; real deployments need authorised, calibrated
  camera feeds and datasets.
- Performance depends on hardware and camera quality.
- AI outputs must be reviewed by a human before any enforcement action.

## Privacy & security
- Privacy-preserving defaults; RTSP credentials are never logged raw or returned by read APIs.
- Configurable data-retention window (`DATA_RETENTION_DAYS`). Audit logs record operator actions.
- Authentication/RBAC structures are in place (users table, roles) but full auth enforcement is
  left as a deployment step for the hackathon MVP.
