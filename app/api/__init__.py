"""Aggregiert alle API-Router unter einem gemeinsamen /api-Präfix."""
from fastapi import APIRouter

from app.api import (
    abstimmungen,
    ereignisse,
    fragen,
    methodik,
    parteien,
    politiker,
    positionen,
    quellen,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(parteien.router)
api_router.include_router(politiker.router)
api_router.include_router(quellen.router)
api_router.include_router(ereignisse.router)
api_router.include_router(abstimmungen.router)
api_router.include_router(positionen.router)
api_router.include_router(methodik.router)
api_router.include_router(fragen.router)
