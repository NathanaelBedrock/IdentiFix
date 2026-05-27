from __future__ import annotations
from core.models import Investigation


def correlate(investigation: Investigation) -> None:
    """
    Enrich the investigation with cross-collector signals.

    Currently detects:
    - Repeated profile hits across different collectors (higher confidence)
    - Shared usernames between email and username searches
    """
    # Collect all profile hits grouped by (platform, username)
    platform_counts: dict[str, int] = {}
    for result in investigation.results:
        for hit in result.profile_hits:
            key = f"{hit.platform.lower()}:{hit.username.lower()}"
            platform_counts[key] = platform_counts.get(key, 0) + 1

    # Tag high-confidence hits (found by 2+ collectors)
    for result in investigation.results:
        for hit in result.profile_hits:
            key = f"{hit.platform.lower()}:{hit.username.lower()}"
            if platform_counts[key] > 1:
                hit.metadata["confirmed_by_multiple"] = True
                hit.metadata["confirmation_count"] = platform_counts[key]

    # Collect all unique emails mentioned in raw data
    emails_found: set[str] = set()
    for result in investigation.results:
        for key, value in result.raw_data.items():
            _extract_emails(value, emails_found)

    if emails_found:
        investigation.target.__dict__.setdefault("correlated_emails", list(emails_found))


def _extract_emails(obj, found: set[str]) -> None:
    import re
    email_re = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    if isinstance(obj, str):
        found.update(email_re.findall(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _extract_emails(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _extract_emails(item, found)
