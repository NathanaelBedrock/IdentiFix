from __future__ import annotations
import asyncio
import httpx
from types import SimpleNamespace
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, EmailBreach
from core.config import settings

try:
    from h8mail.utils.run import target_factory
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _make_user_args(cli_apikeys: list[str] | None) -> SimpleNamespace:
    return SimpleNamespace(
        config_file=None,
        cli_apikeys=cli_apikeys,
        user_query="email_address",
        skip_defaults=False,
        debug=False,
        chase=None,
        chase_limit=10,
        output=None,
        json_output=None,
    )


async def _leaklookup(email: str, api_key: str) -> list[EmailBreach]:
    """Call leak-lookup directly — h8mail silently drops sources with empty data arrays."""
    breaches = []
    try:
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.post(
                "https://leak-lookup.com/api/search",
                data={"key": api_key, "type": "email_address", "query": email},
            )
            data = resp.json()
        if data.get("error") == "false" and isinstance(data.get("message"), dict):
            for source, entries in data["message"].items():
                if not entries:
                    breaches.append(EmailBreach(source=source))
                else:
                    for entry in entries:
                        breaches.append(EmailBreach(
                            source=source,
                            description=str(entry) if entry else None,
                        ))
    except Exception:
        pass
    return breaches


class H8mailCollector(BaseCollector):
    name = "h8mail"
    requires_email = True

    @classmethod
    def available(cls) -> bool:
        return _AVAILABLE

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        email = target.email
        loop = asyncio.get_event_loop()

        cli_apikeys = []
        if settings.h8mail_haveibeenpwned_key:
            cli_apikeys.append(f"hibp={settings.h8mail_haveibeenpwned_key}")
        if settings.h8mail_snusbase_key:
            cli_apikeys.append(f"snusbase_token={settings.h8mail_snusbase_key}")

        # Run h8mail for HIBP / snusbase if keys are configured
        if cli_apikeys:
            user_args = _make_user_args(cli_apikeys)

            def _run():
                return target_factory([email], user_args)

            targets = await loop.run_in_executor(None, _run)
            for t in targets:
                for entry in getattr(t, "data", []):
                    if not isinstance(entry, tuple) or len(entry) < 2:
                        continue
                    source, value = entry[0], entry[1]
                    result.email_breaches.append(EmailBreach(
                        source=str(source),
                        description=str(value) if value else None,
                    ))

        # leak-lookup called directly: h8mail uses wrong query type and drops sources with empty records
        if settings.h8mail_leaklookup_key:
            result.email_breaches.extend(
                await _leaklookup(email, settings.h8mail_leaklookup_key)
            )
