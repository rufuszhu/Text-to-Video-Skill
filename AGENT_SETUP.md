# First-Run Setup For AI Agents

This file is written for an AI coding agent preparing a fresh machine to run `article-video-producer`.

## 1. Confirm The Local Toolchain

Run these checks before producing a video:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

Recommended Python: 3.10-3.12. Qwen3-TTS currently documents Python 3.12 in its setup path.

On macOS, install ffmpeg if missing:

```bash
brew install ffmpeg
```

## 2. Create A Python Environment

Use any environment manager. Example with `uv`:

```bash
uv venv .article-video-venv --python 3.12
source .article-video-venv/bin/activate
uv pip install -U -r requirements.txt
```

Fallback with standard Python:

```bash
python3 -m venv .article-video-venv
source .article-video-venv/bin/activate
python -m pip install -U pip
python -m pip install -U -r requirements.txt
```

## 3. Confirm Image Generation Access

The skill expects an AI image generation tool, preferably OpenAI/ChatGPT Images. In Codex, use the built-in `image_gen` tool when available.

If the environment only supports API/CLI image generation, configure the relevant API key outside the repo. Do not commit secrets.

## 4. Choose The Narration Voice

Use a built-in model voice by default when the user does not provide a voice reference:

```bash
python <skill>/scripts/generate_qwen_narration.py \
  --project <project> \
  --voice-mode model \
  --speaker eric \
  --instruct "Read with a clear documentary narration style." \
  --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
```

For expressive model delivery, write a per-segment JSON file with `id`, `speaker`, and `instruct`, then pass it with `--delivery-plan <path>`.

## 5. Prepare Voice Cloning Inputs

Voice cloning requires consent and a usable reference:

- `audio/voice_reference/reference.wav`: 30-90 seconds of clean speech from the speaker.
- `audio/voice_reference/reference.txt`: exact transcript of that reference audio.

Use only the user's own voice or a voice they have explicit permission to clone. Never clone a public figure or a private person without consent.

Run clone mode explicitly:

```bash
python <skill>/scripts/generate_qwen_narration.py \
  --project <project> \
  --voice-mode clone \
  --ref-audio <project>/audio/voice_reference/reference.wav \
  --ref-text <project>/audio/voice_reference/reference.txt \
  --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
```

`--voice-mode auto` is the default. It uses clone mode when both reference files exist, otherwise it uses model voice mode.

## 6. Expected Run Folder

For each article, create a fresh project folder:

```text
<VaultRoot>/video/<article-stem>-video/
```

All generated files must stay inside that folder. Do not scatter audio, images, subtitles, or render files next to the source article.

## 7. Use Bundled Scripts

Prefer these helpers instead of writing project-local one-off scripts:

```bash
python <skill>/scripts/build_narration_segments.py --project <project>
python <skill>/scripts/generate_qwen_narration.py --project <project> --voice-mode auto --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
python <skill>/scripts/reflow_srt.py --project <project>
python <skill>/scripts/make_contact_sheet.py --project <project>
python <skill>/scripts/render_video.py --project <project>
```

Normalize narration after TTS:

```bash
ffmpeg -i <project>/audio/narration.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 <project>/audio/narration_normalized.wav
```

## 8. Mandatory Human Gates

Stop twice:

1. After writing `script/spoken_script.md`.
2. After writing `images/visual_entities.md`, `images/style_guide.md`, `images/image_plan.md`, and `images/image_prompts.json`.

After image generation, create `images/contact_sheet.html` and pause again before final render unless the user already approved direct rendering.

## 9. Final Verification

Before claiming completion:

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 <project>/audio/narration_normalized.wav
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 <project>/video/final.mp4
ffprobe -v error -select_streams s -show_entries stream=index -of csv=p=0 <project>/video/final.mp4
```

The final MP4 should contain video and audio only. Subtitles must remain external as `video/final.srt`.
