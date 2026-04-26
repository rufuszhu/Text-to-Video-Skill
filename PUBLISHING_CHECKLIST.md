# Publishing Checklist

Use this checklist before making the repository public.

## Required

- Confirm `LICENSE` is present and the MIT copyright owner/year are correct.
- Confirm all docs, samples, comments, and prompts are in English.
- Confirm no private paths, names, voice references, API keys, or generated private videos are committed.
- Confirm `.gitignore` excludes model caches, voice references, local environments, and generated video runs.
- Run a syntax check for bundled Python scripts.
- Run JSON validation for `evals/evals.json`.
- Smoke-test both narration modes, or at least confirm their commands are documented:
  - `--voice-mode model` for built-in Qwen3-TTS CustomVoice speakers.
  - `--voice-mode clone` for consent-based user voice references.

## Recommended

- Render the sample source in `samples/gettysburg-address.md`.
- Upload the sample MP4 to GitHub Releases for the simplest repo-linked demo. Use YouTube as an optional public-facing mirror.
- Replace the placeholder sample link in `README.md`.
- Add a sample poster image or contact sheet if you want a visual preview in the README.
- Add a short note about hardware expectations for Qwen3-TTS on CPU versus GPU.
- Add a first GitHub release after the sample has been rendered and verified.

## Do Not Publish

- Private voice reference audio.
- Private voice reference transcripts.
- API keys or `.env` files.
- Hugging Face model caches.
- Large generated MP4s committed directly to the repo.
- User-specific vault paths or article drafts.

## Suggested Demo Source

Use `samples/gettysburg-address.md` for the first public demo. It is short, public domain, English, and widely recognizable.
