"""
Maigret: full-spectrum username search — subprocess wrapper.
Writes ndjson report to a temp dir and parses the file output.
"""
from __future__ import annotations
import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit


class MaigretCollector(BaseCollector):
    name = "maigret"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("maigret") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username

        with tempfile.TemporaryDirectory() as tmpdir:
            proc = await asyncio.create_subprocess_exec(
                "maigret", username,
                "-J", "ndjson",
                "-fo", tmpdir,
                "--no-progressbar",
                "-a",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=300)

            report = Path(tmpdir) / f"report_{username}_ndjson.json"
            if not report.exists():
                return

            for line in report.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                status_obj = entry.get("status", {})
                if not isinstance(status_obj, dict):
                    continue
                if status_obj.get("status") != "Claimed":
                    continue

                result.profile_hits.append(ProfileHit(
                    platform=entry.get("sitename") or status_obj.get("site_name", "unknown"),
                    url=entry.get("url_user") or status_obj.get("url", ""),
                    username=username,
                    exists=True,
                    metadata={
                        "ids": status_obj.get("ids", {}),
                        "tags": status_obj.get("tags", []),
                        "rank": entry.get("rank"),
                    },
                ))
