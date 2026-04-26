#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


TIME_RE = re.compile(
    r"(?P<h1>\d{2}):(?P<m1>\d{2}):(?P<s1>\d{2}),(?P<ms1>\d{3}) --> "
    r"(?P<h2>\d{2}):(?P<m2>\d{2}):(?P<s2>\d{2}),(?P<ms2>\d{3})"
)
CJK_RE = re.compile(r"[\u3400-\u9fff]")


def parse_time(value: str) -> float:
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def fmt_time(value: float) -> str:
    value = max(0.0, value)
    h = int(value // 3600)
    value -= h * 3600
    m = int(value // 60)
    value -= m * 60
    s = int(value)
    ms = round((value - s) * 1000)
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        match = TIME_RE.match(lines[1])
        if not match:
            continue
        start, end = lines[1].split(" --> ")
        cues.append((parse_time(start), parse_time(end), " ".join(lines[2:])))
    return cues


def remove_repeated_tail(text: str) -> str:
    # Catches duplicated trailing phrases without language-specific hardcoding.
    for size in range(min(24, len(text) // 2), 1, -1):
        chunk = text[-size:]
        if text.endswith(chunk + chunk):
            return text[:-size]
    return text


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("\uff1a  ", "\uff1a")
    text = remove_repeated_tail(text)
    return text


def split_long_clause(clause: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    rest = clause
    while len(rest) > max_chars:
        split_at = -1
        for match in re.finditer(r"\s+", rest[: max_chars + 1]):
            if match.start() >= int(max_chars * 0.55):
                split_at = match.start()
        if split_at == -1:
            split_at = max_chars
        parts.append(rest[:split_at].strip())
        rest = rest[split_at:].strip()
    if rest:
        parts.append(rest)
    return parts


def split_units(text: str, cjk_chars: int, latin_chars: int) -> list[str]:
    text = clean_text(text)
    max_chars = cjk_chars if CJK_RE.search(text) else latin_chars
    if len(text) <= max_chars:
        return [text]

    pieces = re.split("([\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001,.!?;:])", text)
    clauses = []
    for idx in range(0, len(pieces), 2):
        clause = pieces[idx]
        if idx + 1 < len(pieces):
            clause += pieces[idx + 1]
        if clause.strip():
            clauses.append(clause.strip())

    units: list[str] = []
    current = ""
    for clause in clauses or [text]:
        if len(clause) > max_chars:
            if current:
                units.append(current)
                current = ""
            units.extend(split_long_clause(clause, max_chars))
        elif not current:
            current = clause
        elif len(current) + len(clause) <= max_chars:
            current += clause
        else:
            units.append(current)
            current = clause
    if current:
        units.append(current)
    return units


def reflow_cues(
    cues: list[tuple[float, float, str]],
    cjk_chars: int,
    latin_chars: int,
    max_lines: int,
) -> list[tuple[float, float, str]]:
    out = []
    for start, end, text in cues:
        units = split_units(text, cjk_chars, latin_chars)
        grouped = ["\n".join(units[i : i + max_lines]) for i in range(0, len(units), max_lines)]
        if len(grouped) == 1:
            out.append((start, end, grouped[0]))
            continue

        duration = max(0.4, end - start)
        step = duration / len(grouped)
        for idx, group in enumerate(grouped):
            cue_start = start + idx * step
            cue_end = start + (idx + 1) * step
            out.append((cue_start, cue_end, group))
    return out


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> None:
    blocks = []
    for idx, (start, end, text) in enumerate(cues, start=1):
        blocks.append(f"{idx}\n{fmt_time(start)} --> {fmt_time(end)}\n{text}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean, reflow, and copy SRT subtitles.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Article video project folder.")
    parser.add_argument("--input", type=Path, help="Raw input SRT.")
    parser.add_argument("--output", type=Path, help="Aligned/reflowed output SRT.")
    parser.add_argument("--final", type=Path, help="Final sidecar SRT next to final.mp4.")
    parser.add_argument("--qc", type=Path, help="Subtitle QC markdown path.")
    parser.add_argument("--cjk-chars", type=int, default=22)
    parser.add_argument("--latin-chars", type=int, default=42)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--note", action="append", default=[], help="Additional QC note.")
    args = parser.parse_args()

    project = args.project.resolve()
    raw = args.input or project / "subtitles" / "transcript_raw.srt"
    out = args.output or project / "subtitles" / "subtitles_aligned.srt"
    final = args.final or project / "video" / "final.srt"
    qc = args.qc or project / "subtitles" / "subtitle_qc.md"

    cues = parse_srt(raw.read_text(encoding="utf-8"))
    reflowed = reflow_cues(cues, args.cjk_chars, args.latin_chars, args.max_lines)
    write_srt(reflowed, out)
    write_srt(reflowed, final)

    max_line_len = max((len(line) for _, _, text in reflowed for line in text.splitlines()), default=0)
    qc_lines = [
        "# Subtitle QC",
        "",
        f"- Input cues: {len(cues)}.",
        f"- Output cues after reflow: {len(reflowed)}.",
        f"- Max rendered line length: {max_line_len}.",
        "- Removed inline tags and collapsed repeated trailing fragments when detected.",
        "- Timing was inherited from the alignment/transcription tool; text was only reflowed.",
    ]
    qc_lines.extend(f"- {note}" for note in args.note)
    qc.parent.mkdir(parents=True, exist_ok=True)
    qc.write_text("\n".join(qc_lines) + "\n", encoding="utf-8")

    print(f"Wrote {out}")
    print(f"Wrote {final}")
    print(f"Wrote {qc}")
    print(f"Cues: {len(cues)} -> {len(reflowed)}")


if __name__ == "__main__":
    main()
