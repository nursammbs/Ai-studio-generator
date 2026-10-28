#!/usr/bin/env python3
"""Inspect ComfyUI UI/API JSON and show node IDs plus editable input names."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any


def _short(value: Any, limit: int = 90) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        rendered = repr(value)
    return rendered if len(rendered) <= limit else rendered[:limit - 1] + "…"


def inspect_workflow(data: Any) -> tuple[str, str]:
    """Return (format label, readable node report) for a ComfyUI workflow/API prompt."""
    if not isinstance(data, dict):
        raise ValueError("Workflow root must be a JSON object.")
    if isinstance(data.get("prompt"), dict):
        data = data["prompt"]
    if isinstance(data.get("nodes"), list):
        rows = []
        for node in data["nodes"]:
            if not isinstance(node, dict):
                continue
            node_id = node.get("id", "?")
            node_type = str(node.get("type", "unknown"))
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            title = str(node.get("title") or props.get("Node name for S&R") or node_type)
            inputs = node.get("inputs") if isinstance(node.get("inputs"), list) else []
            names = [str(i.get("name") or i.get("label") or "?") for i in inputs if isinstance(i, dict)]
            widgets = node.get("widgets_values")
            rows.append((str(node_id), node_type, title, ", ".join(names) or "—", _short(widgets) if widgets is not None else "—"))
        report = [
            "# ComfyUI node inspection",
            "",
            "**Detected format:** UI workflow graph (nodes array), not the API prompt format used by /prompt.",
            "Export this graph as API format in ComfyUI before using it with studio_pipeline.py.",
            "",
            "| Node ID | Node type | Title | Input ports | UI widget values (not API field names) |",
            "|---|---|---|---|---|",
        ]
        report.extend("| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in rows)
        return "ui", "\n".join(report) + "\n"

    nodes = []
    for node_id, node in data.items():
        if isinstance(node, dict) and isinstance(node.get("inputs"), dict):
            node_type = str(node.get("class_type", "unknown"))
            inputs = node["inputs"]
            input_text = ", ".join(f"{name}={_short(value, 48)}" for name, value in inputs.items()) or "—"
            nodes.append((str(node_id), node_type, input_text))
    if not nodes:
        raise ValueError("No API nodes found. Expected an API prompt object with node IDs and inputs, or a UI graph with nodes.")
    def sort_key(row: tuple[str, str, str]) -> tuple[int, str]:
        try:
            return (0, f"{int(row[0]):012d}")
        except ValueError:
            return (1, row[0])
    nodes.sort(key=sort_key)
    report = [
        "# ComfyUI node inspection",
        "",
        "**Detected format:** API prompt object. Use the node IDs and exact input names below when configuring the shot pipeline.",
        "",
        "| Node ID | Class type | API inputs and current values |",
        "|---|---|---|",
    ]
    report.extend("| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in nodes)
    report += [
        "",
        "Common input names vary by node and workflow. Look for the actual field used for appearance prompt, pose prompt, random seed, reference image, driving video, and generated video output.",
        "The field values shown here may contain internal filenames; do not paste credentials or private paths into public issues.",
        "",
    ]
    return "api", "\n".join(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", type=Path, required=True, help="ComfyUI UI graph or API prompt JSON")
    parser.add_argument("--output", type=Path, help="Optional Markdown report output path")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.workflow.read_text(encoding="utf-8"))
        fmt, report = inspect_workflow(data)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
            print(f"Report saved: {args.output.resolve()}")
        else:
            print(report)
        print(f"Detected format: {fmt.upper()}")
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
