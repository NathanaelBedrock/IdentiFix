from __future__ import annotations
from core.models import Investigation
from core.config import settings


async def generate_ai_report(investigation: Investigation) -> str | None:
    if not settings.openai_api_key:
        return None

    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    summary = investigation.summary()
    target = investigation.target

    platforms = list({
        hit.platform
        for result in investigation.results
        for hit in result.profile_hits
        if hit.exists
    })
    breaches = [
        {"source": b.source, "date": b.date, "fields": b.fields}
        for result in investigation.results
        for b in result.email_breaches
    ]
    registrations = [
        reg.site
        for result in investigation.results
        for reg in result.email_registrations
        if reg.registered
    ]

    prompt = f"""You are an OSINT analyst. Write a structured, professional intelligence report based on the following investigation data.

## Target
- Username: {target.username or 'N/A'}
- Email: {target.email or 'N/A'}
- Twitter/X: {target.twitter_handle or 'N/A'}
- Discord: {target.discord_id or 'N/A'}
- Reddit: {target.reddit_username or 'N/A'}

## Findings
- Total profile hits: {summary['profile_hits']} across {len(platforms)} platforms
- Platforms found: {', '.join(platforms) if platforms else 'None'}
- Email registrations: {summary['email_registrations']} sites
- Data breaches: {summary['email_breaches']}
- Breach details: {breaches if breaches else 'None'}
- Registered email sites: {', '.join(registrations[:20]) if registrations else 'None'}

## Report format
Write: 1) Executive Summary (2-3 sentences), 2) Digital Footprint Analysis, 3) Risk Assessment, 4) Key Identifiers, 5) Recommendations.
Keep it factual, concise, and professional. Do not speculate beyond the data."""

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.3,
    )
    return response.choices[0].message.content
