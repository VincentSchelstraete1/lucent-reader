"""
Interactive labeling scaffold for Lucent Reader session logs.

Loads one or more exported session-log JSON files (from the extension's
"Export Session Log" button), groups events by paragraph, shows you each
paragraph's available signals, and asks you to label whether you
personally found it hard to read. Saves a labeled CSV ready to load into
tomorrow's model-comparison notebook.

Usage:
    python label_dataset.py session1.json [session2.json ...]

Recommended workflow for real labels (not tonight's test data):
    1. Read a real article start to finish, normally, using the extension.
    2. Export the session log when you're done.
    3. Run this script and label based on genuine memory of what felt hard.
    4. Repeat for a few more articles before moving to feature engineering.
"""

import json
import sys
import csv
from pathlib import Path
from collections import defaultdict


def load_events(paths):
    events = []
    for path in paths:
        with open(path) as f:
            events.extend(json.load(f))
    return events


def group_by_paragraph(events):
    """
    Groups events by paragraph identity. This currently falls back to
    grouping by a cleaned textPreview, since paragraph IDs don't exist
    in the log yet - if you add stable per-paragraph IDs in the
    extension later (recommended), swap this to group by
    data["paragraphId"] instead for more reliable grouping, especially
    once real (non-fake) simplified text no longer starts with a
    predictable "[Simplified] " prefix you can strip off to match.
    """
    groups = defaultdict(list)
    for e in events:
        data = e.get("data", {})
        preview = data.get("textPreview")
        if preview:
            key = preview.replace("[Simplified] ", "").strip()[:40]
            groups[key].append(e)
    return groups


def summarize_paragraph(events):
    types = [e["type"] for e in events]
    return {
        "dwell_flag": types.count("dwell_flag"),
        "simplify_click": types.count("simplify_click"),
        "simplify_done": types.count("simplify_done"),
        "revert_click": types.count("revert_click"),
        "total_events": len(events),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python label_dataset.py session1.json [session2.json ...]")
        sys.exit(1)

    events = load_events(sys.argv[1:])
    groups = group_by_paragraph(events)

    print(f"\nFound {len(groups)} distinct paragraphs across {len(sys.argv) - 1} file(s).\n")

    rows = []
    for i, (key, para_events) in enumerate(groups.items(), 1):
        summary = summarize_paragraph(para_events)

        print(f"\n--- Paragraph {i}/{len(groups)} ---")
        print(f"Preview: {key}...")
        print(
            f"Signals: dwell_flag={summary['dwell_flag']}, "
            f"simplify_click={summary['simplify_click']}, "
            f"revert_click={summary['revert_click']}, "
            f"total_events={summary['total_events']}"
        )

        while True:
            label = input("Did you find this paragraph hard to read? (y/n/skip): ").strip().lower()
            if label in ("y", "n", "skip"):
                break
            print("Please type y, n, or skip.")

        if label == "skip":
            continue

        rows.append({
            "paragraph_preview": key,
            **summary,
            "struggled": 1 if label == "y" else 0
        })

    if not rows:
        print("\nNo labels recorded - nothing to save.")
        return

    out_path = Path("labeled_dataset.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} labeled paragraphs to {out_path.resolve()}")


if __name__ == "__main__":
    main()