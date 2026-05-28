"""
Blackbird: Email & username search on 600+ sites.
Invoked as a subprocess. Results are written to a JSON file in cwd,
not stdout — we use a temp dir to capture them cleanly.
"""
from __future__ import annotations
import asyncio
import json
import re
import shutil
import tempfile
from pathlib import Path
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit


def _blackbird_cwd() -> Path | None:
    """Resolve blackbird's install directory from its wrapper script."""
    wrapper = shutil.which("blackbird")
    if not wrapper:
        return None
    try:
        content = Path(wrapper).read_text()
        m = re.search(r'python\s+(\S+blackbird\.py)', content)
        if m:
            return Path(m.group(1)).parent
    except Exception:
        pass
    return None


def _flatten_metadata(raw: list | None) -> dict:
    if not raw:
        return {}
    return {item["name"].lower(): item["value"] for item in raw if "name" in item and "value" in item}


class BlackbirdCollector(BaseCollector):
    name = "blackbird"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("blackbird") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        blackbird_dir = _blackbird_cwd()

        cmd = ["blackbird", "-u", username, "--json"]
        if target.email:
            cmd += ["-e", target.email]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=str(blackbird_dir) if blackbird_dir else None,
        )
        await asyncio.wait_for(proc.communicate(), timeout=120)

        if blackbird_dir is None:
            return

        # Blackbird saves to results/{username}_{date}_blackbird/{username}_{date}_blackbird.json
        matches = list(blackbird_dir.glob(f"results/*{username}*/*blackbird*.json"))
        if not matches:
            return

        report_path = max(matches, key=lambda p: p.stat().st_mtime)
        try:
            entries = json.loads(report_path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        for entry in entries:
            if entry.get("status") != "FOUND":
                continue
            result.profile_hits.append(ProfileHit(
                platform=entry.get("name", "unknown"),
                url=entry.get("url", ""),
                username=username,
                exists=True,
                metadata=_flatten_metadata(entry.get("metadata")),
            ))
