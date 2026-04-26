#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def normalize_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def compact_len(text: str) -> int:
    return len("".join(text.split()))


def estimate_seconds_from_text(text: str, chars_per_second: float) -> float:
    return max(8.0, compact_len(text) / chars_per_second)


def max_tokens_for_text(text: str, chars_per_second: float) -> int:
    estimated_seconds = estimate_seconds_from_text(text, chars_per_second)
    return max(420, min(2200, int(estimated_seconds * 15 + 160)))


def chunk_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = compact_len(paragraph)
        if current and current_len + paragraph_len > max_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = paragraph_len
        else:
            current.append(paragraph)
            current_len += paragraph_len

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def dtype_from_name(torch_module: Any, name: str) -> Any:
    if name == "auto":
        return None
    try:
        return getattr(torch_module, name)
    except AttributeError as exc:
        raise ValueError(f"Unknown torch dtype: {name}") from exc


def read_wav(path: Path) -> tuple[Any, int]:
    import numpy as np
    import soundfile as sf

    wav, sr = sf.read(path, dtype="float32")
    if wav.ndim > 1:
        wav = np.mean(wav, axis=-1).astype(np.float32)
    return wav, int(sr)


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def resolve_voice_mode(requested: str, ref_audio: Path, ref_text: Path) -> str:
    if requested != "auto":
        return requested
    return "clone" if ref_audio.exists() and ref_text.exists() else "model"


def default_model_id(voice_mode: str) -> str:
    if voice_mode == "model":
        return "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    return "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def load_delivery_plan(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(item["id"]): item for item in data if isinstance(item, dict) and "id" in item}
    if isinstance(data, dict):
        if "segments" in data and isinstance(data["segments"], list):
            return {str(item["id"]): item for item in data["segments"] if isinstance(item, dict) and "id" in item}
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}
    raise ValueError(f"Unsupported delivery plan shape: {path}")


def file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"name": path.name, "size": stat.st_size, "mtime": int(stat.st_mtime)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Qwen3-TTS narration from narration_segments.json.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Article video project folder.")
    parser.add_argument("--segments", type=Path, help="Input narration_segments.json.")
    parser.add_argument("--voice-mode", choices=["auto", "clone", "model"], default="auto", help="auto uses clone when reference files exist, otherwise model voice.")
    parser.add_argument("--model-id", help="Qwen3-TTS model id. Defaults to a Base model for clone mode and a CustomVoice model for model mode.")
    parser.add_argument("--speaker", default="eric", help="CustomVoice speaker for --voice-mode model.")
    parser.add_argument("--instruct", default="", help="Global delivery instruction for --voice-mode model.")
    parser.add_argument("--delivery-plan", type=Path, help="Optional JSON with per-segment speaker/instruct overrides.")
    parser.add_argument("--device-map", default="cpu")
    parser.add_argument("--dtype", default="float32", help="torch dtype name, or auto.")
    parser.add_argument("--language", default="Auto")
    parser.add_argument("--hf-cache", type=Path, help="Optional Hugging Face cache root.")
    parser.add_argument("--ref-audio", type=Path, help="Voice reference WAV path.")
    parser.add_argument("--ref-text", type=Path, help="Voice reference transcript path.")
    parser.add_argument("--out", type=Path, help="Output narration WAV.")
    parser.add_argument("--manifest-out", type=Path, help="Output segments_manifest.json.")
    parser.add_argument("--segment-dir", type=Path, help="Directory for per-segment WAV files.")
    parser.add_argument("--chunk-dir", type=Path, help="Directory for per-chunk WAV files.")
    parser.add_argument("--max-chars", type=int, default=220)
    parser.add_argument("--chars-per-second", type=float, default=5.8)
    parser.add_argument("--inter-chunk-silence", type=float, default=0.22)
    parser.add_argument("--inter-segment-silence", type=float, default=0.45)
    parser.add_argument("--force-segments", default=os.environ.get("FORCE_SEGMENTS", ""))
    parser.add_argument("--outlier-ratio", type=float, default=1.6)
    args = parser.parse_args()

    project = args.project.resolve()
    if args.hf_cache:
        os.environ.setdefault("HF_HOME", str(args.hf_cache))
        os.environ.setdefault("HF_HUB_CACHE", str(args.hf_cache / "hub"))

    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    segments_path = args.segments or project / "script" / "narration_segments.json"
    ref_audio = args.ref_audio or project / "audio" / "voice_reference" / "reference.wav"
    ref_text_path = args.ref_text or project / "audio" / "voice_reference" / "reference.txt"
    voice_mode = resolve_voice_mode(args.voice_mode, ref_audio, ref_text_path)
    model_id = args.model_id or default_model_id(voice_mode)
    segment_dir = args.segment_dir or project / "audio" / ("segments_model_voice" if voice_mode == "model" else "segments")
    chunk_dir = args.chunk_dir or project / "audio" / ("segment_chunks_model_voice" if voice_mode == "model" else "segment_chunks")
    manifest_out = args.manifest_out or project / "audio" / "segments_manifest.json"
    out_wav = args.out or project / "audio" / "narration.wav"

    segment_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    force_segments = {item.strip() for item in args.force_segments.split(",") if item.strip()}
    segments = json.loads(segments_path.read_text(encoding="utf-8"))
    delivery_plan = load_delivery_plan(args.delivery_plan)

    ref_text = ""
    voice_prompt = None
    if voice_mode == "clone":
        if not ref_audio.exists() or not ref_text_path.exists():
            raise FileNotFoundError(
                "Voice clone mode requires both reference files: "
                f"{ref_audio} and {ref_text_path}. Use --voice-mode model for built-in voices."
            )
        ref_text = ref_text_path.read_text(encoding="utf-8").strip()

    print(f"Voice mode: {voice_mode}", flush=True)
    print(f"Loading {model_id} on {args.device_map}...", flush=True)
    tts = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=args.device_map,
        dtype=dtype_from_name(torch, args.dtype),
        attn_implementation=None,
    )

    supported_speakers = None
    if voice_mode == "clone":
        print("Building voice clone prompt...", flush=True)
        voice_prompt = tts.create_voice_clone_prompt(
            ref_audio=str(ref_audio),
            ref_text=ref_text,
            x_vector_only_mode=False,
        )
    else:
        supported_speakers = tts.get_supported_speakers()
        if supported_speakers:
            if args.speaker not in supported_speakers:
                raise ValueError(f"Unknown speaker '{args.speaker}'. Supported speakers: {', '.join(supported_speakers)}")
            print(f"Supported speakers: {', '.join(supported_speakers)}", flush=True)

    wav_parts: list[Any] = []
    manifest = []
    current_time = 0.0
    sample_rate = None

    for index, segment in enumerate(segments, start=1):
        segment_id = segment["id"]
        out_path = segment_dir / f"{segment_id}.wav"
        meta_path = segment_dir / f"{segment_id}.json"
        text = normalize_text(segment["text"])
        delivery = delivery_plan.get(segment_id, {})
        speaker = str(delivery.get("speaker", args.speaker))
        instruct = str(delivery.get("instruct", args.instruct)).strip()
        if voice_mode == "model" and supported_speakers and speaker not in supported_speakers:
            raise ValueError(f"Unknown speaker '{speaker}' for {segment_id}. Supported speakers: {', '.join(supported_speakers)}")
        signature = {
            "voice_mode": voice_mode,
            "model_id": model_id,
            "language": args.language,
            "speaker": speaker if voice_mode == "model" else "",
            "instruct": instruct if voice_mode == "model" else "",
            "text_hash": sha1_text(text),
            "ref_audio": file_fingerprint(ref_audio) if voice_mode == "clone" else None,
            "ref_text_hash": sha1_text(ref_text) if voice_mode == "clone" else "",
        }
        print(f"[{index}/{len(segments)}] {segment_id}: {segment.get('title', '')}", flush=True)

        force_segment = segment_id in force_segments
        should_regenerate = True
        if out_path.exists():
            wav, sr = read_wav(out_path)
            duration = len(wav) / sr
            expected = float(segment.get("estimated_seconds", estimate_seconds_from_text(text, args.chars_per_second)))
            existing_signature = None
            if meta_path.exists():
                try:
                    existing_signature = json.loads(meta_path.read_text(encoding="utf-8")).get("signature")
                except json.JSONDecodeError:
                    existing_signature = None
            should_regenerate = force_segment or existing_signature != signature or duration > expected * args.outlier_ratio
            if should_regenerate:
                if force_segment:
                    reason = "forced"
                elif existing_signature != signature:
                    reason = "voice/text settings changed"
                else:
                    reason = f"{duration:.1f}s vs expected {expected:.1f}s"
                print(f"  Regenerating existing segment ({reason}).", flush=True)
            else:
                print(f"  Reusing {out_path.name} ({duration:.1f}s).", flush=True)

        if should_regenerate:
            chunk_wavs = []
            chunk_sr = None
            chunks = chunk_text(text, args.max_chars)
            for chunk_index, chunk in enumerate(chunks, start=1):
                chunk_signature = dict(signature)
                chunk_signature["chunk_hash"] = sha1_text(chunk)
                chunk_hash = sha1_text(json.dumps(chunk_signature, ensure_ascii=False, sort_keys=True))[:12]
                chunk_path = chunk_dir / f"{segment_id}_part_{chunk_index:02d}_{chunk_hash}.wav"
                max_new_tokens = max_tokens_for_text(chunk, args.chars_per_second)
                print(f"  chunk {chunk_index}/{len(chunks)}: {compact_len(chunk)} chars, max_new_tokens={max_new_tokens}", flush=True)

                if chunk_path.exists() and not force_segment:
                    chunk_wav, sr = read_wav(chunk_path)
                else:
                    if voice_mode == "clone":
                        wavs, sr = tts.generate_voice_clone(
                            text=chunk,
                            language=args.language,
                            voice_clone_prompt=voice_prompt,
                            max_new_tokens=max_new_tokens,
                        )
                    else:
                        wavs, sr = tts.generate_custom_voice(
                            text=chunk,
                            speaker=speaker,
                            language=args.language,
                            instruct=instruct or None,
                            max_new_tokens=max_new_tokens,
                        )
                    chunk_wav = np.asarray(wavs[0], dtype=np.float32)
                    sf.write(chunk_path, chunk_wav, sr)

                chunk_sr = int(sr) if chunk_sr is None else chunk_sr
                if int(sr) != chunk_sr:
                    raise RuntimeError(f"Unexpected chunk sample rate for {segment_id}: {sr} != {chunk_sr}")
                chunk_wavs.append(chunk_wav)
                if chunk_index < len(chunks):
                    chunk_wavs.append(np.zeros(int(chunk_sr * args.inter_chunk_silence), dtype=np.float32))

            sr = int(chunk_sr)
            wav = np.concatenate(chunk_wavs)
            sf.write(out_path, wav, sr)
            meta_path.write_text(
                json.dumps(
                    {
                        "signature": signature,
                        "duration": round(float(len(wav) / sr), 3),
                        "sample_rate": sr,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        sample_rate = int(sr) if sample_rate is None else sample_rate
        if int(sr) != sample_rate:
            raise RuntimeError(f"Unexpected sample rate for {segment_id}: {sr} != {sample_rate}")

        duration = float(len(wav) / sample_rate)
        manifest.append(
            {
                "id": segment_id,
                "title": segment.get("title", ""),
                "file": str(out_path.relative_to(project / "audio")),
                "start": round(current_time, 3),
                "end": round(current_time + duration, 3),
                "duration": round(duration, 3),
                "voice_mode": voice_mode,
                "speaker": speaker if voice_mode == "model" else "",
                "instruct": instruct if voice_mode == "model" else "",
                "text": text,
            }
        )
        wav_parts.append(wav)
        current_time += duration

        if index < len(segments):
            silence = np.zeros(int(sample_rate * args.inter_segment_silence), dtype=np.float32)
            wav_parts.append(silence)
            current_time += len(silence) / sample_rate

    final_wav = np.concatenate(wav_parts) if wav_parts else np.array([], dtype=np.float32)
    sf.write(out_wav, final_wav, sample_rate)
    manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {out_wav}", flush=True)
    print(f"Wrote {manifest_out}", flush=True)
    print(f"Sample rate: {sample_rate}", flush=True)
    print(f"Duration: {len(final_wav) / sample_rate:.3f}s", flush=True)


if __name__ == "__main__":
    main()
