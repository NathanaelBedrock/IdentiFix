from __future__ import annotations
import httpx
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ReverseImageMatch
from core.config import settings

SAUCENAO_API = "https://saucenao.com/search.php"


class SauceNAOCollector(BaseCollector):
    name = "saucenao"
    requires_image = True

    @classmethod
    def available(cls) -> bool:
        return bool(settings.saucenao_api_key)

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        with open(target.image_path, "rb") as f:
            image_bytes = f.read()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                SAUCENAO_API,
                data={"api_key": settings.saucenao_api_key, "output_type": 2, "numres": 10},
                files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            )
            resp.raise_for_status()
            data = resp.json()

        for item in data.get("results", []):
            header = item.get("header", {})
            _data = item.get("data", {})
            result.image_matches.append(ReverseImageMatch(
                similarity=float(header.get("similarity", 0)),
                thumbnail_url=header.get("thumbnail"),
                source_url=_data.get("ext_urls", [None])[0],
                title=_data.get("title") or _data.get("source"),
                author=_data.get("author_name") or _data.get("creator"),
                site=header.get("index_name"),
            ))
