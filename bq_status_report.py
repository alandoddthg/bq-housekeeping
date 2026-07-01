import json
import os
import datetime
import argparse
import pandas as pd

# --- CONFIGURATION ---
STATE_FILE = "state.json"
EXCEL_FILE = "20260624_Data_Estate_Cleanup_Audit xlsx.xlsx"
SHEET_NAME = "BQ-added-Data"

STATUS_LABELS = {
    "scream_test": "Scream Test Active",
    "deleted": "Deleted",
    "restored": "Restored",
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def load_audit_context():
    if not os.path.exists(EXCEL_FILE):
        return {}
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    context = {}
    for _, row in df.iterrows():
        key = f"{row['Project']}:{row['Dataset']}"
        context[key] = {
            "size_gb": row.get("Size (GB)"),
            "monthly_cost": row.get("Monthly Cost ($)"),
            "region": row.get("Region"),
            "description": row.get("Description"),
        }
    return context


def days_elapsed(iso_timestamp):
    started = datetime.datetime.fromisoformat(iso_timestamp)
    return (datetime.datetime.now() - started).days


def build_report(state, context, retention_days):
    lines = []
    generated_at = datetime.datetime.now().isoformat()
    lines.append("# BigQuery Decommissioning Status Report")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Source: live `{STATE_FILE}` + `{EXCEL_FILE}` (regenerate this report rather than editing it by hand)")
    lines.append("")

    if not state:
        lines.append("No entries in state.json yet — no Scream Tests have been initiated (or this is dry-run only).")
        return "\n".join(lines)

    by_status = {}
    for key, info in state.items():
        by_status.setdefault(info.get("status", "unknown"), []).append((key, info))

    total_size = 0.0
    total_cost = 0.0

    for status, entries in by_status.items():
        label = STATUS_LABELS.get(status, status)
        lines.append(f"## {label} ({len(entries)})")
        lines.append("")
        lines.append("| Dataset | Tranche | Size (GB) | Monthly Cost ($) | Initiated | Days Elapsed | Ready for Phase D |")
        lines.append("|---|---|---|---|---|---|---|")

        for key, info in sorted(entries):
            ctx = context.get(key, {})
            size_gb = ctx.get("size_gb")
            monthly_cost = ctx.get("monthly_cost")
            if isinstance(size_gb, (int, float)):
                total_size += size_gb
            if isinstance(monthly_cost, (int, float)):
                total_cost += monthly_cost

            initiated_at = info.get("scream_initiated_at", "")
            elapsed = days_elapsed(initiated_at) if initiated_at else None
            ready = "YES" if (elapsed is not None and elapsed >= retention_days and status == "scream_test") else ""

            lines.append(
                f"| {key} | {info.get('tranche', '')} | {size_gb if size_gb is not None else 'n/a'} "
                f"| {monthly_cost if monthly_cost is not None else 'n/a'} | {initiated_at} "
                f"| {elapsed if elapsed is not None else 'n/a'} | {ready} |"
            )
        lines.append("")

    lines.append("## Totals")
    lines.append(f"- Datasets tracked: {len(state)}")
    lines.append(f"- Combined size: {total_size:,.2f} GB")
    lines.append(f"- Combined monthly cost: ${total_cost:,.2f}")

    return "\n".join(lines)


def generate(output_path=None, retention_days=7):
    """Build the report from live state and write it to output_path if given. Returns the report text."""
    state = load_state()
    context = load_audit_context()
    report = build_report(state, context, retention_days)
    if output_path:
        with open(output_path, "w") as f:
            f.write(report)
    return report


def main():
    parser = argparse.ArgumentParser(description="Generate a human-readable status report from state.json")
    parser.add_argument("--retention-days", type=int, default=7, help="Monitoring period used to flag Phase D readiness (default: 7)")
    parser.add_argument("--output", help="Write report to this file instead of stdout")
    args = parser.parse_args()

    report = generate(output_path=args.output, retention_days=args.retention_days)

    if args.output:
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
