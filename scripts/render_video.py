#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str]) -> None:
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def scene_id_for_segment(segment_id: str) -> str:
    return segment_id.replace("seg_", "scene_")


def rel_to(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve()).replace(os.sep, "/")


def build_scenes(manifest: list[dict[str, Any]], project: Path, motion: str) -> list[dict[str, Any]]:
    scenes = []
    for index, item in enumerate(manifest):
        scene_id = scene_id_for_segment(item["id"])
        scene_start = float(item["start"])
        scene_end = float(manifest[index + 1]["start"]) if index + 1 < len(manifest) else float(item["end"])
        scenes.append(
            {
                "scene_id": scene_id,
                "segments": [item["id"]],
                "image": f"../images/{scene_id}.png",
                "start": round(scene_start, 3),
                "end": round(scene_end, 3),
                "duration": round(scene_end - scene_start, 3),
                "motion": motion,
            }
        )
        image_path = project / "images" / f"{scene_id}.png"
        if not image_path.exists():
            raise FileNotFoundError(image_path)
    return scenes


def video_filter(
    scene: dict[str, Any],
    render_index: int,
    width: int,
    height: int,
    fps: int,
    zoom_delta: float,
    x_drift: float,
    y_drift: float,
    motion_oversample: int,
) -> str:
    duration = float(scene["duration"])
    if scene.get("motion") == "static":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},trim=duration={duration},setpts=PTS-STARTPTS,format=yuv420p"
        )

    oversample = max(1, motion_oversample)
    work_width = width * oversample
    work_height = height * oversample
    frames = max(1, round(duration * fps))
    progress_denominator = max(1, frames - 1)
    progress_expr = f"(on/{progress_denominator})"
    x_sign = 1 if render_index % 2 == 0 else -1
    y_sign = -1 if render_index % 3 == 0 else 1
    scaled_x_drift = x_drift * oversample
    scaled_y_drift = y_drift * oversample
    zoom_expr = f"min(1+{zoom_delta}*{progress_expr},1+{zoom_delta})"
    x_expr = f"max(0,min(iw-iw/zoom,iw/2-(iw/zoom/2)+({x_sign * scaled_x_drift})*({progress_expr}-0.5)))"
    y_expr = f"max(0,min(ih-ih/zoom,ih/2-(ih/zoom/2)+({y_sign * scaled_y_drift})*({progress_expr}-0.5)))"
    return (
        f"scale={work_width}:{work_height}:force_original_aspect_ratio=increase,"
        f"crop={work_width}:{work_height},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
        f"d={frames}:s={work_width}x{work_height}:fps={fps},"
        f"scale={width}:{height}:flags=lanczos,"
        f"trim=duration={duration},setpts=PTS-STARTPTS,format=yuv420p"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render final.mp4 from scene images, narration audio, and sidecar SRT.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Article video project folder.")
    parser.add_argument("--manifest", type=Path, help="audio/segments_manifest.json path.")
    parser.add_argument("--audio", type=Path, help="Narration WAV path.")
    parser.add_argument("--srt", type=Path, help="Sidecar SRT path.")
    parser.add_argument("--output", type=Path, help="Final MP4 path.")
    parser.add_argument("--timeline", type=Path, help="Output timeline JSON path.")
    parser.add_argument("--segment-dir", type=Path, help="Temporary render segment directory.")
    parser.add_argument("--concat-file", type=Path, help="ffmpeg concat file path.")
    parser.add_argument("--visual-track", type=Path, help="Temporary visual-only MP4 path.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--motion", choices=["ultra_slow_pan_zoom", "static"], default="static")
    parser.add_argument("--zoom-delta", type=float, default=0.018)
    parser.add_argument("--x-drift", type=float, default=10.0)
    parser.add_argument("--y-drift", type=float, default=6.0)
    parser.add_argument("--motion-oversample", type=int, default=2, help="Render pan/zoom at a higher resolution before downscaling to reduce pixel-step stutter.")
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", default="20")
    parser.add_argument("--dry-run", action="store_true", help="Write timeline and validate inputs without running ffmpeg.")
    args = parser.parse_args()

    project = args.project.resolve()
    manifest_path = args.manifest or project / "audio" / "segments_manifest.json"
    audio = args.audio or project / "audio" / "narration_normalized.wav"
    srt = args.srt or project / "video" / "final.srt"
    output = args.output or project / "video" / "final.mp4"
    timeline_path = args.timeline or project / "video" / "timeline.json"
    segment_dir = args.segment_dir or project / "video" / "render_segments"
    concat_file = args.concat_file or project / "video" / "render_concat.txt"
    visual_track = args.visual_track or project / "video" / "visual_track.mp4"

    if not audio.exists():
        raise FileNotFoundError(audio)
    if not srt.exists():
        raise FileNotFoundError(srt)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenes = build_scenes(manifest, project, args.motion)
    timeline = {
        "fps": args.fps,
        "width": args.width,
        "height": args.height,
        "audio": rel_to(audio, timeline_path.parent),
        "sidecar_subtitles": rel_to(srt, timeline_path.parent),
        "burn_in_subtitles": False,
        "scenes": scenes,
    }
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {timeline_path}")
    if args.dry_run:
        print("Dry run complete; skipped ffmpeg rendering.")
        return

    segment_dir.mkdir(parents=True, exist_ok=True)
    concat_lines = []
    for render_index, scene in enumerate(scenes):
        image = project / scene["image"].replace("../", "")
        out = segment_dir / f"{scene['scene_id']}.mp4"
        vf = video_filter(
            scene,
            render_index,
            args.width,
            args.height,
            args.fps,
            args.zoom_delta,
            args.x_drift,
            args.y_drift,
            args.motion_oversample,
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-loop",
                "1",
                "-i",
                str(image),
                "-vf",
                vf,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                args.preset,
                "-crf",
                args.crf,
                "-pix_fmt",
                "yuv420p",
                "-t",
                f"{float(scene['duration']):.3f}",
                str(out),
            ]
        )
        concat_lines.append(f"file '{out.resolve()}'")

    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    print(f"Wrote {concat_file}")

    run(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(visual_track)])
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(visual_track),
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
