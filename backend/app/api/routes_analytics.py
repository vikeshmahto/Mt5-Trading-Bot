from fastapi import APIRouter
from typing import List
from app.journal.analytics import get_analytics_summary, get_equity_curve, get_win_rate_breakdown

router = APIRouter()

@router.get("/analytics/summary")
def analytics_summary():
    return get_analytics_summary()

@router.get("/analytics/equity-curve")
def equity_curve():
    return get_equity_curve()

@router.get("/analytics/win-rate-breakdown")
def win_rate_breakdown():
    return get_win_rate_breakdown()
