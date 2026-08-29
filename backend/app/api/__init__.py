"""Aggregate API router."""
from fastapi import APIRouter

from app.api.routers import (
    analysis, calibration, cameras, demo, detections, devices, mongo, system, vehicles,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(cameras.router)
api_router.include_router(devices.router)
api_router.include_router(calibration.router)
api_router.include_router(vehicles.router)
api_router.include_router(detections.router)
api_router.include_router(analysis.router)
api_router.include_router(demo.router)
api_router.include_router(mongo.router)
