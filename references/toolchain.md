# Toolchain Notes

This reference captures the recommended tools and fallback choices for article-to-video production.

## TTS And Voice Cloning

Use Qwen3-TTS only for this skill unless it is impossible to install or run.

- Qwen3-TTS: default TTS and voice cloning engine. Apache-2.0. Supports Chinese and other major languages, reference-based voice cloning, voice design, custom voices, and streaming generation.
- Voice cloning mode: use `Qwen/Qwen3-TTS-12Hz-1.7B-Base` or `Qwen/Qwen3-TTS-12Hz-0.6B-Base`.
- Non-cloned narration mode: use `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` or `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`.
- The bundled narration helper exposes this as `--voice-mode auto|model|clone`. `auto` clones only when both reference files exist; otherwise it uses a CustomVoice model speaker.
- Model voices can receive global delivery guidance through `--instruct` or segment-specific delivery guidance through `--delivery-plan`.

Basic setup from the Qwen3-TTS README:

```bash
conda create -n qwen3-tts python=3.12 -y
conda activate qwen3-tts
pip install -U qwen-tts
```

For source installs:

```bash
git clone https://github.com/QwenLM/Qwen3-TTS.git
cd Qwen3-TTS
pip install -e .
```

FlashAttention 2 can reduce GPU memory usage on compatible hardware:

```bash
pip install -U flash-attn --no-build-isolation
```

## Subtitles

Preferred:

- stable-ts: best fit when the script text is already correct and the task is to align it to generated narration. Export SRT as the final sidecar subtitle file.

Fallback:

- faster-whisper: fast ASR and good for initial transcription. Use it when there is no trusted script or when stable-ts is unavailable. Always run a correction/calibration pass against the intended script.
- WhisperX: useful for word-level timestamps and diarization, but alignment support depends on available language-specific alignment models.

## Image Generation

Use OpenAI/ChatGPT image generation. Prefer the current GPT Image model available in the environment. At the time of research, official OpenAI docs describe GPT Image models including `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini`.

For consistency:

- Write a style guide first.
- Repeat the style constraints in every prompt.
- Reuse reference images or previous generated images when the tool supports image inputs.
- Prefer documentary-realistic editorial visuals over sci-fi or futuristic concept art unless the article calls for that style.
- Include named public figures and other concrete visual entities when they help explain the segment.
- Use short generated text only when useful: map labels, dates, arrows, document titles, numbers, or brief annotations. Avoid visible name labels for universally recognizable public figures unless the user asks for them. Do not rely on generated text for mission-critical wording.

## Video Rendering

Default:

- ffmpeg still-image slideshow with static images for reliable rendering from a JSON timeline. Use optional ultra-slow pan/zoom only when the user explicitly asks for motion or approves a short test render.
- Use the bundled `scripts/render_video.py` helper before writing any one-off render script.

Optional motion:

- Very slow ffmpeg `zoompan` can show pixel-step stutter because crop coordinates are effectively quantized. The bundled renderer uses oversampling before downscaling to reduce this, but static images remain the fallback whenever motion is not visibly smooth.

Use Remotion when needed:

- Remotion for controlled layout, motion graphics, transitions, or other animation-heavy videos. It supports CLI rendering with `npx remotion render`.

Fallback:

- ffmpeg for assembling images/audio and encoding final MP4.
- Do not burn subtitles into the MP4. Produce `final.mp4` plus `final.srt`.

Python fallback:

- MoviePy/Pillow can assemble image/audio video if Remotion is unavailable. It should not render subtitle text into the frames.

## Bundled Helpers

- `scripts/build_narration_segments.py`: deterministic segment JSON/plain text builder.
- `scripts/generate_qwen_narration.py`: chunked Qwen3-TTS narration generator with segment reuse and duration sanity checks.
- `scripts/reflow_srt.py`: SRT cleanup, mobile reflow, final sidecar copy, and subtitle QC.
- `scripts/make_contact_sheet.py`: HTML and optional PNG preview sheet for generated scene images.
- `scripts/render_video.py`: ffmpeg MP4 render with external subtitles only.

## Sources Checked

- Qwen3-TTS: https://github.com/QwenLM/Qwen3-TTS
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- stable-ts: https://github.com/jianfch/stable-ts
- Remotion captions: https://www.remotion.dev/docs/captions/
- Remotion CLI render: https://www.remotion.dev/docs/cli/render
- OpenAI image generation: https://developers.openai.com/api/docs/guides/image-generation
