"""Naminter: username search with smart filtering — subprocess wrapper."""
from __future__ import annotations
import asyncio
import json
import shutil
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit


class NaminterCollector(BaseCollector):
    name = "naminter"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("naminter") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        proc = await asyncio.create_subprocess_exec(
            "naminter", "--username", username, "--output", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return
        for entry in data if isinstance(data, list) else data.get("results", []):
            result.profile_hits.append(ProfileHit(
                platform=entry.get("site", "unknown"),
                url=entry.get("url", ""),
                username=username,
                exists=True,
                metadata=entry,
            ))
