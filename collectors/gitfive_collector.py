"""GitFive: GitHub user intelligence — subprocess wrapper."""
from __future__ import annotations
import asyncio
import json
import shutil
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit


class GitFiveCollector(BaseCollector):
    name = "gitfive"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("gitfive") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        proc = await asyncio.create_subprocess_exec(
            "gitfive", "user", username, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return

        result.raw_data["gitfive"] = data
        result.profile_hits.append(ProfileHit(
            platform="GitHub",
            url=f"https://github.com/{username}",
            username=username,
            exists=True,
            metadata=data,
        ))
