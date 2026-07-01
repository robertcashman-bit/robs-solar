import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.adapters.factory import get_adapter
from app.auth.sessions import SESSION_COOKIE, session_manager
from app.config import settings
from app.schemas.domain import AdapterError
from app.services.ev_load_detector import sync_ev_detector

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    token = websocket.cookies.get(SESSION_COOKIE)
    session = session_manager.read_session(token)
    if not session:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    adapter = get_adapter()
    try:
        while True:
            try:
                metrics = await adapter.get_live_metrics()
                await sync_ev_detector(metrics)
                await websocket.send_json(json.loads(metrics.model_dump_json()))
            except AdapterError as exc:
                await websocket.send_json({"error": str(exc)})
            await asyncio.sleep(settings.poll_interval_live_seconds)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
        await websocket.close(code=1011)
