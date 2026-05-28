"""NameTrace: name origin & gender prediction — HTTP API wrapper."""
from __future__ import annotations
import asyncio
import httpx
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget

GENDERIZE_API = "https://api.genderize.io"
NATIONALIZE_API = "https://api.nationalize.io"


def _merge_nationalities(first: list[dict], last: list[dict]) -> list[dict]:
    """Weighted average: 25% first name, 75% last name (surnames are stronger signals)."""
    scores: dict[str, float] = {}
    for entry in first:
        scores[entry["country_id"]] = scores.get(entry["country_id"], 0) + 0.25 * entry["probability"]
    for entry in last:
        scores[entry["country_id"]] = scores.get(entry["country_id"], 0) + 0.75 * entry["probability"]
    return sorted(
        [{"country_id": k, "probability": round(v, 4)} for k, v in scores.items()],
        key=lambda x: x["probability"],
        reverse=True,
    )[:5]


async def fetch_nametrace(first_name: str, last_name: str | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [
            client.get(GENDERIZE_API, params={"name": first_name}),
            client.get(NATIONALIZE_API, params={"name": first_name}),
        ]
        if last_name:
            tasks.append(client.get(NATIONALIZE_API, params={"name": last_name}))
        results = await asyncio.gather(*tasks)

    gender_data = results[0].json() if results[0].status_code == 200 else {}
    nation_first = results[1].json().get("country", []) if results[1].status_code == 200 else []

    if last_name and results[2].status_code == 200:
        nation_last = results[2].json().get("country", [])
        nationalities = _merge_nationalities(nation_first, nation_last)
    else:
        nationalities = nation_first[:5]

    return {
        "gender": gender_data.get("gender"),
        "gender_probability": gender_data.get("probability"),
        "nationalities": nationalities,
    }


class NameTraceCollector(BaseCollector):
    name = "nametrace"

    def can_run(self, target: InvestigationTarget) -> bool:
        return bool(target.username)

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        first_name = (target.username or "").split()[0][:50]
        data = await fetch_nametrace(first_name)
        result.raw_data["nametrace"] = {"name": first_name, **data}
