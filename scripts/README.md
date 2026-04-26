# Article Video Producer Scripts

Reusable helpers for the article-video-producer skill. Run them with `python` from any working directory and pass `--project <run-folder>`.

Typical sequence after the script and visual plan are approved:

```bash
python scripts/build_narration_segments.py --project <project>
python scripts/generate_qwen_narration.py --project <project> --voice-mode auto --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
ffmpeg -i <project>/audio/narration.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 <project>/audio/narration_normalized.wav
python scripts/reflow_srt.py --project <project>
python scripts/make_contact_sheet.py --project <project>
python scripts/render_video.py --project <project>
```

Voice selection:

- `--voice-mode model --speaker eric --instruct "..."` uses Qwen3-TTS CustomVoice without a reference recording.
- `--voice-mode clone --ref-audio reference.wav --ref-text reference.txt` uses a permitted voice reference.
- `--voice-mode auto` chooses clone mode when reference files exist, otherwise model mode.

The render helper always keeps subtitles external. It writes `video/final.mp4` and expects `video/final.srt` to already exist. It renders static images by default; use `--motion ultra_slow_pan_zoom` only when the user explicitly wants motion and the test render looks smooth.
