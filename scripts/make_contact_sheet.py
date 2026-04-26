#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def rel(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def load_prompts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_excerpt(text: str, limit: int = 360) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def write_html(project: Path, images_dir: Path, prompts: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    prompt_by_file = {item.get("filename"): item for item in prompts}
    image_paths = sorted(images_dir.glob("scene_*.png")) + sorted(images_dir.glob("scene_*.jpg"))

    cards = []
    for image_path in image_paths:
        item = prompt_by_file.get(image_path.name, {})
        scene_id = item.get("scene_id") or image_path.stem
        people = ", ".join(item.get("people_to_show", [])) or "none"
        text = ", ".join(item.get("visible_text", [])) or "none"
        prompt = prompt_excerpt(item.get("prompt", ""))
        image_src = html.escape(image_path.relative_to(out.parent).as_posix())
        cards.append(
            f"""
      <article class="card">
        <img src="{image_src}" alt="{html.escape(scene_id)}" loading="lazy">
        <div class="meta">
          <h2>{html.escape(scene_id)}</h2>
          <p><b>People:</b> {html.escape(people)}</p>
          <p><b>Visible text:</b> {html.escape(text)}</p>
          <details>
            <summary>Prompt</summary>
            <p>{html.escape(prompt)}</p>
          </details>
        </div>
      </article>"""
        )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Article Video Image Contact Sheet</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f1ec;
      color: #1c1b19;
    }}
    body {{
      margin: 0;
      padding: 28px;
    }}
    header {{
      max-width: 1180px;
      margin: 0 auto 22px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
      font-weight: 700;
    }}
    .sub {{
      margin: 0;
      color: #5c5851;
      font-size: 14px;
    }}
    .grid {{
      max-width: 1180px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 18px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #d8d1c7;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 1px 2px rgba(0,0,0,.05);
    }}
    img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      background: #ddd;
    }}
    .meta {{
      padding: 12px 14px 14px;
      font-size: 13px;
      line-height: 1.45;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 15px;
    }}
    p {{
      margin: 4px 0;
    }}
    details {{
      margin-top: 8px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Article Video Image Contact Sheet</h1>
    <p class="sub">Project: {html.escape(str(project))}</p>
  </header>
  <main class="grid">
    {''.join(cards)}
  </main>
</body>
</html>
"""
    out.write_text(html_text, encoding="utf-8")


def write_png(images_dir: Path, out: Path, columns: int, thumb_width: int) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    image_paths = sorted(images_dir.glob("scene_*.png")) + sorted(images_dir.glob("scene_*.jpg"))
    if not image_paths:
        return False

    thumb_height = round(thumb_width * 9 / 16)
    label_height = 34
    gap = 14
    margin = 20
    rows = (len(image_paths) + columns - 1) // columns
    width = margin * 2 + columns * thumb_width + (columns - 1) * gap
    height = margin * 2 + rows * (thumb_height + label_height) + (rows - 1) * gap

    sheet = Image.new("RGB", (width, height), "#f4f1ec")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("Arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    for idx, image_path in enumerate(image_paths):
        row, col = divmod(idx, columns)
        x = margin + col * (thumb_width + gap)
        y = margin + row * (thumb_height + label_height + gap)
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            im.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (thumb_width, thumb_height), "#ddd")
            ox = (thumb_width - im.width) // 2
            oy = (thumb_height - im.height) // 2
            canvas.paste(im, (ox, oy))
            sheet.paste(canvas, (x, y))
        draw.text((x, y + thumb_height + 8), image_path.stem, fill="#1c1b19", font=font)

    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an HTML and optional PNG contact sheet for generated scene images.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Article video project folder.")
    parser.add_argument("--images-dir", type=Path, help="Images directory.")
    parser.add_argument("--prompts", type=Path, help="image_prompts.json path.")
    parser.add_argument("--html-out", type=Path, help="Output contact_sheet.html path.")
    parser.add_argument("--png-out", type=Path, help="Output contact_sheet.png path.")
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument("--thumb-width", type=int, default=640)
    args = parser.parse_args()

    project = args.project.resolve()
    images_dir = args.images_dir or project / "images"
    prompts_path = args.prompts or images_dir / "image_prompts.json"
    html_out = args.html_out or images_dir / "contact_sheet.html"
    png_out = args.png_out or images_dir / "contact_sheet.png"

    prompts = load_prompts(prompts_path)
    write_html(project, images_dir, prompts, html_out)
    print(f"Wrote {html_out}")

    if write_png(images_dir, png_out, args.columns, args.thumb_width):
        print(f"Wrote {png_out}")
    else:
        print("Skipped PNG contact sheet because Pillow is unavailable or no images were found.")


if __name__ == "__main__":
    main()
