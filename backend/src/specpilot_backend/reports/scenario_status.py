from __future__ import annotations

import json
from collections.abc import Sequence
from html import escape

from specpilot_backend.services.persistence import ScenarioRecord


def render_scenario_status_report(records: Sequence[ScenarioRecord]) -> str:
    total = len(records)
    pass_count = sum(1 for record in records if record.latest_result == "pass")
    fail_count = sum(1 for record in records if record.latest_result == "fail")
    review_count = sum(
        1 for record in records if record.latest_result == "needs_review"
    )
    not_run_count = total - pass_count - fail_count - review_count
    pass_rate = (pass_count / total * 100) if total else 0.0

    rows = "\n".join(_render_row(record) for record in records)
    if not rows:
        rows = (
            '<tr><td colspan="5" class="empty">'
            "暂无测试场景"
            "</td></tr>"
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>SpecPilot 场景通过率报告</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #64748b;
      --line: #dbe3ef;
      --pass: #047857;
      --fail: #b91c1c;
      --warn: #b45309;
      --pending: #475569;
      --surface: #f8fafc;
    }}
    body {{
      margin: 0;
      background: #ffffff;
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      letter-spacing: 0;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin: 24px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
      background: var(--surface);
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
    }}
    .metric strong {{
      display: block;
      margin-top: 4px;
      font-size: 24px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: var(--surface);
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0;
      white-space: nowrap;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      min-width: 54px;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 13px;
      font-weight: 600;
    }}
    .status-pass {{
      background: #ecfdf5;
      color: var(--pass);
    }}
    .status-fail {{
      background: #fef2f2;
      color: var(--fail);
    }}
    .status-review {{
      background: #fffbeb;
      color: var(--warn);
    }}
    .status-not-run {{
      background: #f1f5f9;
      color: var(--pending);
    }}
    .empty {{
      color: var(--muted);
      text-align: center;
    }}
  </style>
</head>
<body>
  <main>
    <h1>SpecPilot 场景通过率报告</h1>
    <section class="summary" aria-label="汇总">
      <div class="metric"><span>通过率</span><strong>{pass_rate:.1f}%</strong></div>
      <div class="metric"><span>全部场景</span><strong>{total}</strong></div>
      <div class="metric"><span>通过</span><strong>{pass_count}</strong></div>
      <div class="metric"><span>失败</span><strong>{fail_count}</strong></div>
      <div class="metric"><span>未执行</span><strong>{not_run_count}</strong></div>
    </section>
    <table>
      <thead>
        <tr>
          <th>场景</th>
          <th>优先级</th>
          <th>难度</th>
          <th>审核状态</th>
          <th>最新结果</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def _render_row(record: ScenarioRecord) -> str:
    return (
        "<tr>"
        f"<td>{escape(_scenario_title(record))}</td>"
        f"<td>{escape(record.priority)}</td>"
        f"<td>{escape(_difficulty_label(record.difficulty))}</td>"
        f"<td>{escape(_review_label(record.review_status))}</td>"
        f"<td>{_status_badge(record.latest_result)}</td>"
        "</tr>"
    )


def _scenario_title(record: ScenarioRecord) -> str:
    try:
        payload = json.loads(record.payload_json)
    except json.JSONDecodeError:
        return "未命名场景"
    title = payload.get("title")
    return str(title) if title else "未命名场景"


def _difficulty_label(value: str) -> str:
    return {
        "simple": "简单",
        "medium": "中等",
        "hard": "困难",
    }.get(value, value)


def _review_label(value: str) -> str:
    return {
        "auto_validated": "自动通过",
        "needs_review": "待审核",
        "rejected": "已拒绝",
    }.get(value, value)


def _status_badge(value: str | None) -> str:
    if value == "pass":
        status_key, label = "pass", "通过"
    elif value == "fail":
        status_key, label = "fail", "失败"
    elif value == "needs_review":
        status_key, label = "review", "待复核"
    else:
        status_key, label = "not-run", "未执行"
    return (
        f'<span class="status status-{status_key}">'
        f"{escape(label)}"
        "</span>"
    )
