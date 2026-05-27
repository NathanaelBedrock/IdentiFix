from __future__ import annotations
from core.models import Investigation


def generate_html_report(investigation: Investigation) -> str:
    target = investigation.target
    summary = investigation.summary()

    profile_rows = ""
    for result in investigation.results:
        for hit in result.profile_hits:
            confirmed = "✓" if hit.metadata.get("confirmed_by_multiple") else ""
            profile_rows += (
                f"<tr><td>{hit.platform}</td>"
                f"<td><a href='{hit.url}' target='_blank'>{hit.url}</a></td>"
                f"<td>{hit.username}</td><td>{confirmed}</td></tr>\n"
            )

    email_reg_rows = ""
    for result in investigation.results:
        for reg in result.email_registrations:
            if reg.registered:
                email_reg_rows += (
                    f"<tr><td>{reg.site}</td>"
                    f"<td><a href='{reg.url or ''}' target='_blank'>{reg.url or '-'}</a></td></tr>\n"
                )

    breach_rows = ""
    for result in investigation.results:
        for b in result.email_breaches:
            breach_rows += (
                f"<tr><td>{b.source}</td><td>{b.date or '-'}</td>"
                f"<td>{b.records or '-'}</td><td>{', '.join(b.fields[:5])}</td></tr>\n"
            )

    ai_section = ""
    if investigation.ai_report:
        ai_html = investigation.ai_report.replace("\n", "<br>")
        ai_section = f"""
        <section>
          <h2>AI Intelligence Report</h2>
          <div class="ai-report">{ai_html}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>IdentiFix Report — {target.label()}</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 2rem; }}
    h1 {{ color: #38bdf8; }}
    h2 {{ color: #7dd3fc; border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem; }}
    .stats {{ display: flex; gap: 1rem; margin: 1rem 0; }}
    .stat {{ background: #1e293b; border-radius: 8px; padding: 1rem 1.5rem; text-align: center; }}
    .stat-value {{ font-size: 2rem; font-weight: bold; color: #38bdf8; }}
    .stat-label {{ color: #94a3b8; font-size: 0.85rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th {{ background: #1e293b; padding: 0.5rem; text-align: left; color: #94a3b8; font-size: 0.85rem; }}
    td {{ padding: 0.5rem; border-bottom: 1px solid #1e293b; }}
    a {{ color: #38bdf8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .ai-report {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; line-height: 1.7; }}
    section {{ margin-bottom: 2.5rem; }}
    .badge {{ background: #0ea5e9; color: white; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <h1>IdentiFix OSINT Report</h1>
  <p>Target: <strong>{target.label()}</strong> &nbsp; | &nbsp; Generated: {investigation.completed_at or investigation.created_at}</p>

  <div class="stats">
    <div class="stat"><div class="stat-value">{summary['profile_hits']}</div><div class="stat-label">Profile Hits</div></div>
    <div class="stat"><div class="stat-value">{summary['email_registrations']}</div><div class="stat-label">Email Registrations</div></div>
    <div class="stat"><div class="stat-value">{summary['email_breaches']}</div><div class="stat-label">Data Breaches</div></div>
    <div class="stat"><div class="stat-value">{summary['collectors_run']}/{summary['collectors_total']}</div><div class="stat-label">Collectors Run</div></div>
  </div>

  <section>
    <h2>Profile Hits</h2>
    <table>
      <tr><th>Platform</th><th>URL</th><th>Username</th><th>Confirmed</th></tr>
      {profile_rows or '<tr><td colspan="4">No profile hits found</td></tr>'}
    </table>
  </section>

  <section>
    <h2>Email Registrations</h2>
    <table>
      <tr><th>Site</th><th>URL</th></tr>
      {email_reg_rows or '<tr><td colspan="2">No email registrations found</td></tr>'}
    </table>
  </section>

  <section>
    <h2>Data Breaches</h2>
    <table>
      <tr><th>Source</th><th>Date</th><th>Records</th><th>Fields</th></tr>
      {breach_rows or '<tr><td colspan="4">No breaches found</td></tr>'}
    </table>
  </section>

  {ai_section}
</body>
</html>"""
