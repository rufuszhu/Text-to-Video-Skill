#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(
    r"^(\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e]+[\u5c42\u90e8\u5206\u7ae0\u8282]|"
    r"\u7b2c\s*\d+\s*[\u5c42\u90e8\u5206\u7ae0\u8282]|"
    r"Part\s+\d+|Section\s+\d+|Chapter\s+\d+|Conclusion|\u7ed3\u8bba|\u6700\u540e)",
    re.IGNORECASE,
)


def compact_len(text: str) -> int:
    return len("".join(text.split()))


def estimate_seconds(text: str, chars_per_second: float) -> int:
    return max(8, round(compact_len(text) / chars_per_second))


def clean_for_narration(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^#{1,6}\s+", "", line).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    return "\n".join(lines).strip()


def title_from_text(text: str, fallback: str) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), fallback)
    first = re.sub("[\u3002\uff01\uff1f.!?].*$", "", first).strip()
    return first[:80] or fallback


def slice_by_markers(full_text: str, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for idx, item in enumerate(plan, start=1):
        start = item["start"]
        end = item.get("end")
        start_index = full_text.index(start)
        end_index = len(full_text) if not end else full_text.index(end)
        raw_text = full_text[start_index:end_index].strip()
        text = clean_for_narration(raw_text)
        segment_id = item.get("id") or f"seg_{idx:03d}"
        segments.append(
            {
                "id": segment_id,
                "title": item.get("title") or title_from_text(text, segment_id),
                "text": text,
                "visual_intent": item.get("visual_intent", ""),
            }
        )
    return segments


def split_by_sections(full_text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", full_text.strip()) if p.strip()]
    if not paragraphs:
        return []

    section_starts = [0]
    for idx, paragraph in enumerate(paragraphs[1:], start=1):
        first_line = paragraph.splitlines()[0].strip()
        if SECTION_RE.match(first_line):
            section_starts.append(idx)

    if len(section_starts) <= 1:
        return paragraphs

    chunks = []
    for pos, start_idx in enumerate(section_starts):
        end_idx = section_starts[pos + 1] if pos + 1 < len(section_starts) else len(paragraphs)
        chunks.append("\n\n".join(paragraphs[start_idx:end_idx]))
    return chunks


def merge_or_split_chunks(chunks: list[str], target_segments: int, max_chars: int) -> list[str]:
    if not chunks:
        return []

    # Split oversized chunks on paragraph boundaries first.
    split_chunks: list[str] = []
    for chunk in chunks:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chunk) if p.strip()]
        current: list[str] = []
        current_len = 0
        for paragraph in paragraphs:
            paragraph_len = compact_len(paragraph)
            if current and current_len + paragraph_len > max_chars:
                split_chunks.append("\n\n".join(current))
                current = [paragraph]
                current_len = paragraph_len
            else:
                current.append(paragraph)
                current_len += paragraph_len
        if current:
            split_chunks.append("\n\n".join(current))

    # If there are too many very small chunks, merge neighbors.
    while len(split_chunks) > target_segments:
        best_idx = min(
            range(len(split_chunks) - 1),
            key=lambda idx: compact_len(split_chunks[idx]) + compact_len(split_chunks[idx + 1]),
        )
        merged = split_chunks[best_idx] + "\n\n" + split_chunks[best_idx + 1]
        split_chunks[best_idx : best_idx + 2] = [merged]

    return split_chunks


def auto_segments(full_text: str, target_segments: int, max_chars: int) -> list[dict[str, Any]]:
    chunks = merge_or_split_chunks(split_by_sections(full_text), target_segments, max_chars)
    segments = []
    for idx, chunk in enumerate(chunks, start=1):
        text = clean_for_narration(chunk)
        segment_id = f"seg_{idx:03d}"
        title = title_from_text(text, segment_id)
        segments.append(
            {
                "id": segment_id,
                "title": title,
                "text": text,
                "visual_intent": f"Visualize the argument turn: {title}",
            }
        )
    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description="Build narration_segments.json and spoken_script.txt.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Article video project folder.")
    parser.add_argument("--input", type=Path, help="Spoken script markdown path.")
    parser.add_argument("--plan", type=Path, help="Optional JSON marker plan with start/end strings.")
    parser.add_argument("--segments-out", type=Path, help="Output narration_segments.json path.")
    parser.add_argument("--plain-out", type=Path, help="Output plain text script path.")
    parser.add_argument("--target-segments", type=int, default=10)
    parser.add_argument("--max-chars", type=int, default=750, help="Approx compact chars per segment.")
    parser.add_argument("--chars-per-second", type=float, default=5.8)
    args = parser.parse_args()

    project = args.project.resolve()
    input_path = args.input or project / "script" / "spoken_script.md"
    segments_out = args.segments_out or project / "script" / "narration_segments.json"
    plain_out = args.plain_out or project / "script" / "spoken_script.txt"

    full_text = input_path.read_text(encoding="utf-8").strip()
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        segments = slice_by_markers(full_text, plan)
    else:
        segments = auto_segments(full_text, args.target_segments, args.max_chars)

    for segment in segments:
        segment["estimated_seconds"] = estimate_seconds(segment["text"], args.chars_per_second)

    segments_out.parent.mkdir(parents=True, exist_ok=True)
    plain_out.parent.mkdir(parents=True, exist_ok=True)
    segments_out.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plain_out.write_text("\n\n".join(segment["text"] for segment in segments) + "\n", encoding="utf-8")

    print(f"Wrote {segments_out}")
    print(f"Wrote {plain_out}")
    print(f"Segments: {len(segments)}")
    print(f"Estimated duration: {sum(s['estimated_seconds'] for s in segments)}s")


if __name__ == "__main__":
    main()
