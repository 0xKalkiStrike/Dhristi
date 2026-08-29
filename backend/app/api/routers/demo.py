"""One-click demo control."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import AuditLog
from app.services import demo as demo_service

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/start")
def start_demo(db: Session = Depends(get_db)):
    result = demo_service.start_demo(db)
    db.add(AuditLog(action="demo.start", entity="system", entity_id="demo", detail=result))
    db.commit()
    return {"message": "DRISHTI-V demo started", **result}


@router.post("/stop")
def stop_demo(db: Session = Depends(get_db)):
    result = demo_service.stop_demo()
    db.add(AuditLog(action="demo.stop", entity="system", entity_id="demo"))
    db.commit()
    return {"message": "demo stopped", **result}


@router.post("/setup")
def setup_demo(db: Session = Depends(get_db)):
    dataset = demo_service.setup_demo(db)
    return {"message": "demo dataset prepared", "cameras": [d["camera_id"] for d in dataset],
            "dataset": dataset}
