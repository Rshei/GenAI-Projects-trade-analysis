from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path


def build_trade_dashboard(
    summary_path: str = "results/analytics/trade_history_summary.json",
    output_path: str = "results/analytics/trade_dashboard.html",
) -> str:
    summary_file = Path(summary_path)
    if not summary_file.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")

    with summary_file.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    overview = summary.get("overview", {})
    recent = summary.get("recent_snapshots", [])

    rows = []
    for item in recent:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('source_snapshot_as_of', '')))}</td>"
            f"<td>{html.escape(str(item.get('evaluated_at', '')))}</td>"
            f"<td>{html.escape(str(item.get('trades', 0)))}</td>"
            f"<td>{html.escape(str(item.get('average_return_pct', 0.0)))}</td>"
            f"<td>{html.escape(str(item.get('win_rate_pct', 0.0)))}</td>"
            "</tr>"
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    html_doc = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Trade History Dashboard</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; color: #1f2937; }}
    h1 {{ margin-bottom: 8px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 10px; margin: 14px 0 20px; }}
    .kpi {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; background: #f9fafb; }}
    .kpi .label {{ font-size: 12px; color: #4b5563; }}
    .kpi .value {{ font-size: 20px; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f3f4f6; }}
    .meta {{ margin-top: 20px; font-size: 12px; color: #6b7280; }}
  </style>
</head>
<body>
  <h1>Trade History Summary</h1>
  <div class=\"kpis\">
    <div class=\"kpi\"><div class=\"label\">Snapshots</div><div class=\"value\">{overview.get('snapshots_analyzed', 0)}</div></div>
    <div class=\"kpi\"><div class=\"label\">Trades</div><div class=\"value\">{overview.get('trades_analyzed', 0)}</div></div>
    <div class=\"kpi\"><div class=\"label\">Avg Return %</div><div class=\"value\">{overview.get('current_average_return_pct', 0.0)}</div></div>
    <div class=\"kpi\"><div class=\"label\">Win Rate %</div><div class=\"value\">{overview.get('current_win_rate_pct', 0.0)}</div></div>
  </div>

  <h2>Recent Snapshots</h2>
  <table>
    <thead>
      <tr>
        <th>Source Snapshot As Of</th>
        <th>Evaluated At</th>
        <th>Trades</th>
        <th>Avg Return %</th>
        <th>Win Rate %</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <div class=\"meta\">Generated: {html.escape(generated_at)}</div>
</body>
</html>
"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    path = build_trade_dashboard()
    print(path)
