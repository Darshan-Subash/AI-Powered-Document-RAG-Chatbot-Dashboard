from fastapi import APIRouter
from app import database

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats():
    return database.dashboard_stats()
