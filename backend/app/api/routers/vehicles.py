"""Vehicle intelligence: listing, selective search, detail & journey."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models import Vehicle, VehicleJourney
from app.schemas import JourneyOut, VehicleDetail, VehicleOut, VehicleSearchQuery
from app.services import search as search_service

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleOut])
def list_vehicles(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(Vehicle).order_by(Vehicle.last_seen.desc()).limit(limit)).all()
    return rows


@router.get("/search")
def search(
    plate: str | None = None, vehicle_type: str | None = None, color: str | None = None,
    camera_id: str | None = None, min_speed: float | None = None, max_speed: float | None = None,
    event_type: str | None = None, min_confidence: float | None = None, direction: str | None = None,
    limit: int = Query(100, le=500), db: Session = Depends(get_db),
):
    q = VehicleSearchQuery(
        plate=plate, vehicle_type=vehicle_type, color=color, camera_id=camera_id,
        min_speed=min_speed, max_speed=max_speed, event_type=event_type,
        min_confidence=min_confidence, direction=direction, limit=limit,
    )
    results = search_service.search_vehicles(db, q)
    return {"count": len(results), "results": results}


@router.get("/{vehicle_uid}", response_model=VehicleDetail)
def vehicle_detail(vehicle_uid: str, db: Session = Depends(get_db)):
    detail = search_service.vehicle_detail(db, vehicle_uid)
    if not detail:
        raise NotFoundError("vehicle not found")
    return detail


@router.get("/{vehicle_uid}/journey", response_model=JourneyOut)
def vehicle_journey(vehicle_uid: str, db: Session = Depends(get_db)):
    j = db.scalar(select(VehicleJourney).where(VehicleJourney.vehicle_uid == vehicle_uid))
    if not j:
        raise NotFoundError("journey not found")
    return j
