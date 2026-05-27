from __future__ import annotations
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Any
from core.models import Investigation, InvestigationStatus, SSEEvent
from core.config import settings


class InvestigationStore:
    """In-memory store with optional JSON persistence."""

    def __init__(self):
        self._store: dict[str, Investigation] = {}
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def get(self, inv_id: str) -> Investigation | None:
        return self._store.get(inv_id)

    def all(self) -> list[Investigation]:
        return list(self._store.values())

    def save(self, investigation: Investigation) -> None:
        self._store[investigation.id] = investigation
        self._persist(investigation)

    def delete(self, inv_id: str) -> bool:
        if inv_id not in self._store:
            return False
        del self._store[inv_id]
        path = settings.data_path / f"{inv_id}.json"
        path.unlink(missing_ok=True)
        return True

    def subscribe(self, inv_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(inv_id, []).append(q)
        return q

    def unsubscribe(self, inv_id: str, q: asyncio.Queue) -> None:
        queues = self._queues.get(inv_id, [])
        try:
            queues.remove(q)
        except ValueError:
            pass

    def emit(self, inv_id: str, event: SSEEvent) -> None:
        for q in self._queues.get(inv_id, []):
            q.put_nowait(event)

    def _persist(self, investigation: Investigation) -> None:
        try:
            path = settings.data_path / f"{investigation.id}.json"
            path.write_text(investigation.model_dump_json(indent=2))
        except Exception:
            pass

    def load_all(self) -> None:
        for path in settings.data_path.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                inv = Investigation.model_validate(data)
                self._store[inv.id] = inv
            except Exception:
                pass


store = InvestigationStore()
store.load_all()


async def event_stream(inv_id: str) -> AsyncGenerator[dict[str, Any], None]:
    q = store.subscribe(inv_id)
    try:
        while True:
            try:
                event: SSEEvent = await asyncio.wait_for(q.get(), timeout=30)
                yield {"event": event.event, "data": json.dumps(event.data)}
                if event.event in ("completed", "failed", "cancelled"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
    finally:
        store.unsubscribe(inv_id, q)
