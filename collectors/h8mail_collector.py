from __future__ import annotations
import asyncio
from types import SimpleNamespace
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, EmailBreach
from core.config import settings

try:
    from h8mail.utils.run import target_factory, target
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _make_user_args(cli_apikeys: list[str] | None) -> SimpleNamespace:
    return SimpleNamespace(
        config_file=None,
        cli_apikeys=cli_apikeys,
        user_query=None,
        skip_defaults=False,
        debug=False,
        chase=None,
        chase_limit=10,
        output=None,
        json_output=None,
    )


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
            cli_apikeys.append(f"hibp:{settings.h8mail_haveibeenpwned_key}")
        if settings.h8mail_snusbase_key:
            cli_apikeys.append(f"snusbase:{settings.h8mail_snusbase_key}")

        user_args = _make_user_args(cli_apikeys or None)

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
