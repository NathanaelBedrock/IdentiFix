"""NameTrace: name origin & gender prediction — HTTP API wrapper."""
from __future__ import annotations
import asyncio
import httpx
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget

GENDERIZE_API = "https://api.genderize.io"
NATIONALIZE_API = "https://api.nationalize.io"


async def fetch_nametrace(first_name: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        gender_resp, nation_resp = await asyncio.gather(
            client.get(GENDERIZE_API, params={"name": first_name}),
            client.get(NATIONALIZE_API, params={"name": first_name}),
        )
    gender_data = gender_resp.json() if gender_resp.status_code == 200 else {}
    nation_data = nation_resp.json() if nation_resp.status_code == 200 else {}
    return {
        "gender": gender_data.get("gender"),
        "gender_probability": gender_data.get("probability"),
        "nationalities": nation_data.get("country", [])[:5],
    }


class NameTraceCollector(BaseCollector):
    name = "nametrace"

    def can_run(self, target: InvestigationTarget) -> bool:
        # Works on first name extracted from username or full name field
        return bool(target.username)

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        first_name = (target.username or "").split()[0][:50]
        data = await fetch_nametrace(first_name)
        result.raw_data["nametrace"] = {"name": first_name, **data}
