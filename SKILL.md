---
name: article-video-producer
description: Use when producing a narrated video from an article, Obsidian note, essay, newsletter, Markdown file, or script, especially when the task involves Qwen3-TTS narration, sidecar SRT subtitles, image generation, ffmpeg/Remotion rendering, or fixing subtitle/image timing in an explainer-style video workflow.
---

# Article Video Producer

Use this skill to convert a written article into a complete narrated video package: adapted script, voiceover audio, subtitle files, image prompts/assets, scene plan, and a rendered video.

The goal is not to rewrite the author into a different person. Preserve the article's argument structure, rhetorical rhythm, and signature phrasing while making it speakable for a video host.

The output video should not have burned-in subtitles. Produce an external `.srt` file next to the final video so the user can upload it as a selectable subtitle track.

## Output Contract

At the start of each run, create a fresh project folder under the user's vault:

```text
<VaultRoot>/video/<article-stem>-video/
```

If that folder already exists, append a timestamp such as `<article-stem>-video-YYYYMMDD-HHMMSS`. Store every generated artifact for the run inside this folder. Do not scatter outputs next to the source article.

```text
<article-stem>-video/
|-- script/
|   |-- original.md
|   |-- spoken_script.md
|   `-- narration_segments.json
|-- audio/
|   |-- voice_reference/        # optional, user-provided
|   |-- narration.wav
|   `-- narration_normalized.wav
|-- subtitles/
|   |-- transcript_raw.srt
|   |-- subtitles_aligned.srt
|   `-- subtitle_qc.md
|-- images/
|   |-- visual_entities.md
|   |-- style_guide.md
|   |-- image_plan.md
|   |-- image_prompts.json
|   |-- contact_sheet.html
|   |-- contact_sheet.png       # optional, when Pillow is available
|   `-- scene_###.png
|-- video/
|   |-- timeline.json
|   |-- render_project/         # Remotion or other renderer files if used
|   |-- final.mp4
|   `-- final.srt               # copy of the final sidecar subtitles
`-- production_notes.md
```

If the full render cannot be completed because a local model, GPU, API key, or video dependency is missing, still produce every upstream artifact possible and write exact next commands in `production_notes.md`.

Treat the tree above as an in-progress production workspace. After the final video has been verified and the user asks for cleanup or has opted into cleanup for the run, compact the workspace using the retention policy below. Do not delete working files before final verification.

Default retained archive after cleanup:

- Final MP4 and sidecar SRT in `video/`.
- Final normalized narration audio in `audio/`.
- Final scene images in `images/scene_###.png`.
- Image prompts and image plan in `images/image_prompts.json` and `images/image_plan.md`.
- Approved spoken script in `script/spoken_script.md`.
- `production_notes.md`.

Everything else is considered reproducible working data unless the user asks to preserve it: raw TTS chunks, per-segment audio files, unnormalized narration WAVs, intermediate subtitle/alignment files, visual-track MP4s, render segment clips, concat lists, QC frames, copied one-off helper scripts, contact sheets, voice-reference copies, older alternate renders, and timeline/debug JSON files. When multiple final versions exist, confirm which version is canonical before deleting the older MP4/SRT/audio pair.

## Bundled Scripts

Prefer the reusable scripts in this skill's `scripts/` directory over writing one-off project-local scripts:

| Script | Purpose |
|---|---|
| `scripts/build_narration_segments.py` | Build `script/narration_segments.json` and `script/spoken_script.txt` from the approved spoken script, optionally using a marker plan. |
| `scripts/generate_qwen_narration.py` | Generate Qwen3-TTS model-voice or cloned narration in per-segment chunks, reuse good segments, detect obvious duration outliers, and write `audio/segments_manifest.json`. Pair it with post-TTS audio QC before treating the narration as final. |
| `scripts/reflow_srt.py` | Clean stable-ts/faster-whisper SRT output, remove inline tags, reflow cues for mobile readability, copy `video/final.srt`, and write `subtitle_qc.md`. |
| `scripts/make_contact_sheet.py` | Create `images/contact_sheet.html` and, when Pillow is available, `images/contact_sheet.png` for quick visual review before rendering. |
| `scripts/render_video.py` | Render `video/final.mp4` from scene images, audio, and sidecar SRT using ffmpeg, with external subtitles only. |

## Mandatory User Confirmation Gates

Every run has two required pause points:

1. After `script/spoken_script.md` is written, pause for user review. Continue only after the user confirms; reread the edited script from disk before moving on.
2. After `images/visual_entities.md`, `images/style_guide.md`, `images/image_plan.md`, and `images/image_prompts.json` are written, pause for user review. Continue only after the user confirms; reread the edited visual plan and prompts from disk before generating images.

These gates are part of the workflow even when the draft looks good. The user may edit the saved files between turns, and those edits override the previous draft.

After images are generated, also create a contact sheet preview. If the user has not explicitly pre-approved final rendering after image generation, pause and ask them to quickly review the contact sheet for incorrect people, style drift, bad text, or obvious image failures before rendering the final MP4.

## Workflow

### 1. Inspect Inputs

Read the article first, resolve `VaultRoot`, and immediately create the run folder at `<VaultRoot>/video/<article-stem>-video/` before generating other files. If it is an Obsidian note, preserve wikilinks and frontmatter in `script/original.md` but remove them from the spoken script unless they carry meaning.

Ask for missing essentials only when they block production:

- Target aspect ratio: default to `16:9` for YouTube/Bilibili unless the user says Shorts/TikTok/Reels, then use `9:16`.
- Voice reference audio: required only for voice cloning. Use a non-cloned fallback voice if absent.
- Video length preference: infer from script length when not specified.

Detect the article's primary language and keep the narration in that language by default. For mixed-language articles, use the dominant language for narration and preserve names, quotes, terms of art, tickers, and phrases that are intentionally in another language.

### 2. Adapt The Script

Transform the article into `script/spoken_script.md`:

- Keep the original framework and section order.
- Keep the author's core language style, recurring terms, and analytical stance.
- Make sentences more speakable: shorter clauses, fewer dense nested structures, more oral transitions.
- Do not soften controversial claims unless the user asks; preserve the argument's force.
- Add light host-like connective tissue only where it improves listening flow.
- Keep numbers, names, and key claims intact unless there is an obvious typo.
- Mark optional pauses with short paragraph breaks, not stage directions.

After writing `script/spoken_script.md`, stop and ask the user to review it. Tell the user they can edit the file directly, then reply when they want to continue. Do not generate narration, subtitles, image plans, images, timelines, or video until the user confirms.

When the user confirms, reread `script/spoken_script.md` from disk and treat the edited file as the source of truth. Then create `script/narration_segments.json` with segment objects. Prefer `scripts/build_narration_segments.py`; if you need precise AI-chosen section boundaries, write a small marker plan and pass it with `--plan`.

```json
[
  {
    "id": "seg_001",
    "title": "Opening thesis",
    "text": "Narration text for this segment...",
    "visual_intent": "What the image should communicate",
    "estimated_seconds": 18
  }
]
```

Use segment boundaries where the argument naturally turns: introduction, each major section, important examples, and conclusion. Prefer 6-14 visual segments for a 5-12 minute essay video; avoid one image per sentence.

### 3. Generate TTS With Qwen3-TTS

Use **Qwen3-TTS** as the TTS engine. Do not spend time comparing TTS alternatives unless Qwen3-TTS is impossible to install or run in the user's environment.

Choose the Qwen3-TTS mode:

- Use `Qwen/Qwen3-TTS-12Hz-1.7B-Base` or `0.6B-Base` with `generate_voice_clone` when the user provides a voice reference and transcript.
- Use `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` or `0.6B-CustomVoice` with `generate_custom_voice` when no voice reference is provided.
- Use `--voice-mode auto` unless the user explicitly asks for a specific voice path. Auto mode uses clone mode only when both `audio/voice_reference/reference.wav` and `audio/voice_reference/reference.txt` exist; otherwise it uses model voice mode.
- For model voices, choose a supported speaker such as `eric` and pass concise delivery guidance with `--instruct`. For segment-specific tone changes, write a JSON delivery plan containing segment `id`, `speaker`, and `instruct`, then pass `--delivery-plan`.
- Pass the article language explicitly when confident; otherwise use `Auto` when Qwen3-TTS supports it for the chosen model.
- Prefer the 1.7B model for final narration quality and the 0.6B model for faster drafts or lower-memory machines.

If Qwen3-TTS cannot be installed or run, stop at the upstream artifacts and write the blocker plus exact next commands in `production_notes.md` rather than silently switching to another TTS engine.

Voice cloning safety:

- Use only the user's own voice or a voice they have permission to clone.
- Do not imitate a public figure or private person without consent.
- Keep the original reference audio in `audio/voice_reference/`; do not overwrite it.

Generate `audio/narration.wav`, then normalize loudness to `audio/narration_normalized.wav` with ffmpeg if available:

```bash
ffmpeg -i audio/narration.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 audio/narration_normalized.wav
```

For longer scripts, split each narration segment into sentence- or paragraph-level chunks before sending text to Qwen3-TTS, then concatenate the chunk audio back into the segment. This prevents runaway generations and makes failures cheap to retry. After generation, write `audio/segments_manifest.json` and sanity-check every segment duration against the expected script length; rerun obvious outliers instead of letting a bad segment propagate into subtitles and rendering.

Post-TTS audio QC is mandatory before subtitle alignment or rendering:

- Keep the chunk- and segment-level intermediates until narration QC passes. Do not clean up `audio/segments/`, `audio/segment_chunks/`, or `audio/segments_manifest.json` immediately after a seemingly successful generation.
- Check each chunk and each assembled segment for long low-energy spans, not just total duration. A failed generation may contain audible room tone, hiss, or other background noise instead of digital silence.
- Use `ffmpeg` low-energy detection as the first-pass screen. `silencedetect` is acceptable even when the bad region is not perfectly silent, as long as the `noise` threshold is tuned high enough to classify the noisy tail as low-energy non-speech.
- Treat long low-energy spans in the middle of narration as defects even if the total segment duration looks plausible. A good default policy is to flag mid-segment low-energy regions over roughly 2-3 seconds and suspicious tail regions over roughly 1-2 seconds.
- If the first-pass thresholding is ambiguous because the noise floor is high or unstable, run a second-pass speech-presence check on only the suspicious chunk or span. Use VAD, ASR alignment coverage, or another "is there actually speech here?" check rather than relying on waveform energy alone.
- Prefer the cheapest repair that removes the defect: regenerate only the bad chunk when possible, otherwise regenerate the affected segment and rebuild downstream audio/subtitles from there.
- Do not proceed to subtitle alignment, image-to-audio timing, or final render until the narration passes this QC.

Prefer `scripts/generate_qwen_narration.py` for this step:

```bash
python /path/to/article-video-producer/scripts/generate_qwen_narration.py --project <project-folder> --voice-mode auto --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
```

Model voice example:

```bash
python /path/to/article-video-producer/scripts/generate_qwen_narration.py --project <project-folder> --voice-mode model --speaker eric --instruct "Read with a sober documentary tone." --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
```

Voice clone example:

```bash
python /path/to/article-video-producer/scripts/generate_qwen_narration.py --project <project-folder> --voice-mode clone --ref-audio <project-folder>/audio/voice_reference/reference.wav --ref-text <project-folder>/audio/voice_reference/reference.txt --hf-cache <VaultRoot>/article-video-setup/model-cache/huggingface
```

### 4. Generate And Calibrate Subtitles

Do not assume the TTS system emits usable subtitles. Most TTS tools produce audio only or coarse timing.

Preferred subtitle path:

1. Use `stable-ts` to align the known-correct narration text to `audio/narration_normalized.wav`.
2. Export SRT for compatibility.
3. If `stable-ts` is unavailable, use `faster-whisper` to transcribe audio into SRT, then run a calibration pass against `spoken_script.md`.

For the alignment text source:

- Prefer `script/spoken_script.txt` when it exists. It is the cleanest exact-text alignment input because it strips markdown headings and formatting while preserving the approved spoken wording.
- If `script/spoken_script.txt` does not exist, use the approved `script/spoken_script.md` content after removing markdown-only structure that should not be spoken.
- Do not align from `script/original.md` unless the spoken script is intentionally identical.

Calibration pass:

- Compare the subtitle text with the spoken script.
- Fix ASR errors, missing punctuation, wrong names, wrong numbers, and language-specific homophone or tokenization mistakes.
- Keep timing from the aligned/transcribed result unless the text correction changes segment length dramatically.
- Write `subtitles/subtitle_qc.md` with any unresolved mismatches.

Final-delivery rule:

- When `stable-ts` is available and can align the approved narration text, treat that aligned timing as the final subtitle source of truth.
- Segment-derived, sentence-weighted, or manifest-estimated subtitle timing is acceptable only as a draft fallback when true alignment is unavailable or clearly broken. Do not ship those estimated timings as the final sidecar SRT when `stable-ts` worked.
- If `stable-ts` partially fails, preserve the aligned result, document the imperfect portions in `subtitle_qc.md`, and only patch the affected regions instead of discarding the whole alignment.

After the alignment/transcription tool writes `subtitles/transcript_raw.srt`, prefer `scripts/reflow_srt.py` for cleanup and sidecar copying:

```bash
python /path/to/article-video-producer/scripts/reflow_srt.py --project <project-folder>
```

For subtitles:

- Keep lines short enough for mobile, max 2 lines.
- For CJK languages, usually target 12-18 characters per line.
- For alphabetic languages, usually target 32-42 characters per line.
- Split at punctuation and rhetorical pauses.
- Preserve key foreign-language terms, names, tickers, and numbers exactly.
- Copy the final SRT to `video/final.srt`. Do not burn captions into `video/final.mp4`.

### 5. Plan Images

Before writing prompts, extract visual entities into `images/visual_entities.md`:

- Real people named in the article, especially public figures and office holders.
- Places, institutions, maps, physical objects, documents, weapons, ships, buildings, and recurring abstractions that can anchor the visuals.
- Which scenes should show each person or entity, and whether a short label would help viewers understand the image.
- Any people who should be avoided or anonymized because they are private individuals or the script does not support showing them.

When the article names real public figures, include them in relevant images by default. Use recognizable, respectful, documentary/editorial likenesses or clearly labeled news-style portraits. Do not fabricate compromising, illegal, or intimate actions that the script does not claim happened. If a scene discusses several named actors, prefer a realistic composite, diplomatic-table scene, news-wall layout, or split-frame portrait arrangement rather than an empty symbolic image.

Create `images/style_guide.md` before generating any images. The style guide should define:

- Overall visual language.
- Color palette.
- Camera/framing vocabulary.
- Recurring motifs.
- Aspect ratio and resolution.
- Things to avoid.
- Entity/person coverage rules.
- How short visible text, labels, maps, arrows, dates, or document snippets may be used.

Default visual style:

- Prefer grounded documentary realism: contemporary news magazine stills, real-world locations, natural lighting, plausible materials, human-scale framing, and editorial photo-illustration.
- Avoid sci-fi, futuristic command centers, holograms, neon dashboards, glowing maps, floating UI, fantasy armor, overly glossy concept art, and generic apocalypse imagery unless the article is actually about those things.
- People should appear whenever they clarify the argument. For political/geopolitical essays, avoid long stretches of empty symbols when the article is about concrete leaders, negotiators, militaries, or institutions.
- Use short readable text when it helps comprehension: country labels, map labels, dates, treaty/document titles, arrows, numbers, or one- to three-word concept annotations. Do not rely on image text for the main argument, avoid long paragraphs inside images, and avoid name labels for universally recognizable public figures unless the user asks for them.
- Avoid fake official insignia, fake newspaper mastheads, invented seals, or misleading "archival photo" cues unless the prompt makes the image clearly editorial or illustrative.

For argument-heavy articles, prefer documentary-realist editorial stills, news-photo-style composites, realistic geopolitical tableaux, maps or documents with light annotation, and public-figure portraits. Use abstract visual metaphors only when no concrete person, place, document, or event would communicate the segment better. Avoid generic stock-photo business people unless the article truly calls for them.

Create both a human-readable `images/image_plan.md` and a structured `images/image_prompts.json`. The plan must show how the narration is divided into visual scenes, which script segments each scene covers, the intended timing or duration source, and the exact prompt for each scene.

```json
[
  {
    "scene_id": "scene_001",
    "segments": ["seg_001", "seg_002"],
    "duration_source": "subtitle_time_range_or_estimate",
    "people_to_show": ["public figure or role names, if relevant"],
    "visible_text": ["short labels or annotations, if helpful"],
    "prompt": "Full image prompt...",
    "negative_prompt": "Avoid...",
    "filename": "scene_001.png"
  }
]
```

Every image prompt should repeat the realism/style constraints needed for consistency. For scenes with named public figures, include the names in the prompt and describe the role they play in the scene. For scenes where labels help, specify the exact visible text and keep it short enough for an image model to render.

After writing `images/visual_entities.md`, `images/style_guide.md`, `images/image_plan.md`, and `images/image_prompts.json`, stop and ask the user to review the visual segmentation and prompts. Tell the user they can edit any of these files directly, then reply when they want image generation to begin. Do not call OpenAI/ChatGPT image generation or create image files until the user confirms.

When the user confirms, reread `images/visual_entities.md`, `images/style_guide.md`, `images/image_plan.md`, and `images/image_prompts.json` from disk. Use the edited files as the source of truth for image generation and the later timeline.

Use OpenAI/ChatGPT image generation for final assets. Prefer the current GPT Image model available in the environment. Keep all prompts in one consistent style family. Because image models can drift across generations, repeat the style guide's key constraints in every prompt and reuse reference images when the tool supports it.

Do not ask the image model to render long or mission-critical text inside images; subtitles handle the exact argument. Short map labels, dates, numbers, arrows, document headings, and concept labels are encouraged when they improve comprehension. Avoid visible name labels for universally recognizable public figures unless the user asks for them.

After all scene images exist, create a contact sheet before rendering:

```bash
python /path/to/article-video-producer/scripts/make_contact_sheet.py --project <project-folder>
```

Use the contact sheet to check public-figure coverage, style consistency, bad generated text, obvious artifacts, and whether the images still feel like the approved visual plan.

### 6. Build The Timeline

Create `video/timeline.json` by mapping image scenes to subtitle/audio time ranges:

```json
{
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "audio": "../audio/narration_normalized.wav",
  "sidecar_subtitles": "../subtitles/subtitles_aligned.srt",
  "scenes": [
    {
        "image": "../images/scene_001.png",
        "start": 0.0,
        "end": 24.6,
        "motion": "static"
    }
  ]
}
```

Use subtitle time ranges as the source of truth once subtitles exist. Before subtitles exist, use narration segment estimates and revise later.

If the approved visual plan has more image scenes than narration segments, do not collapse back to one image per narration segment. Build a scene-level timeline by splitting the segment window at subtitle/audio anchor points from the approved image plan so each planned scene gets its own start/end range.

Use `static` as the default motion mode. Static images are more reliable for long narrated essays because very slow ffmpeg pan/zoom can show pixel-step stutter on some images and players. Use `ultra_slow_pan_zoom` only when the user explicitly asks for motion or approves it after seeing a test render. If any pan/zoom looks jittery, re-render with `static` rather than trying to hide the artifact. When mapping scenes to narration segments, include inter-segment pauses so the visual track never ends before the audio; a scene should usually run until the next scene starts, and the final scene should run through the audio end.

### 7. Render Video

Preferred renderer: ffmpeg still-image slideshow with static images unless the user asks for motion, layout overlays, or richer motion graphics. Use Remotion only when the video needs controlled layout, transitions, or animated elements. Remotion can be driven from `timeline.json`.

Use ffmpeg directly for simple slideshow-style renders. For `static`, render each still image as an unmoving clip. For optional `ultra_slow_pan_zoom`, use the bundled renderer's oversampled mode so ffmpeg renders motion at a higher resolution and downsamples to reduce pixel-step stutter; still re-render static if the result is not smooth. Because subtitles are external sidecar files, ffmpeg does not need `libass`, `subtitles`, or `drawtext` support.

Prefer `scripts/render_video.py` for the ffmpeg render when the visual track is effectively one scene per narration segment:

```bash
python /path/to/article-video-producer/scripts/render_video.py --project <project-folder>
```

If the visual plan introduces multiple scenes inside one narration segment, first build a scene-level `video/timeline.json` from subtitle/audio anchors and then render from that scene-level timeline. Do not force the project back into one image per narration segment just because the default renderer is simpler.

After rendering `video/final.mp4`, copy `subtitles/subtitles_aligned.srt` to `video/final.srt`. Keep the subtitle file separate from the video.

If only the sidecar subtitle timing or wording needs correction, regenerate and replace `video/final.srt` without rerendering `video/final.mp4`. Sidecar subtitle fixes do not require an MP4 rerender unless the visual timeline itself is changing.

Keep the final output:

- H.264 MP4, `yuv420p`, AAC audio.
- `1920x1080` for landscape or `1080x1920` for vertical.
- External SRT subtitle file beside the video, named `final.srt`.
- No image or subtitle should end before its corresponding audio.

### 8. Quality Check

Before calling the work done:

- Play or inspect the final video duration with `ffprobe`.
- Review narration audio before or alongside final video QC. Sample suspicious regions from the chunk, segment, and full narration levels instead of trusting the muxed MP4 alone.
- Confirm there are no long low-energy or no-speech spans inside spoken sections. Do not rely solely on full-file duration checks.
- Verify audio duration and video duration differ by less than 0.5 seconds.
- Confirm subtitles start near 0 and end before or at audio end.
- Confirm `video/final.mp4` has no burned-in subtitle text and `video/final.srt` exists.
- Sample at least three timestamps: beginning, middle, end. Confirm frames are not black, not cropped badly, and any optional pan/zoom is genuinely smooth; if motion stutters, re-render static.
- Check all generated images exist, match aspect ratio, use a consistent documentary-realistic style, and are not sci-fi/futuristic unless specifically requested.
- Open or inspect `images/contact_sheet.html` before final rendering unless the user explicitly pre-approved direct rendering.
- Check that important named public figures and visual entities from `images/visual_entities.md` appear in the planned scenes, or note why they were omitted.
- Check that any visible text requested in the prompts is short, useful, and not misleading.
- Read `subtitle_qc.md`; unresolved text mismatches must be mentioned to the user.

### 9. Cleanup After Approval

If the user asks to clean the project after the final render, keep the compact archive described in the Output Contract and remove reproducible intermediates. Before deleting, identify the canonical final version and make sure its MP4, SRT, normalized audio, scene images, image prompts/plan, spoken script, and production notes exist.

Do not clean up narration intermediates before the narration has passed post-TTS QC and any required subtitle/audio rebuilds are complete.

For the default cleanup profile, keep:

- `video/final*.mp4` only for the canonical final version.
- `video/final*.srt` only for the canonical final version.
- `audio/*normalized*.wav` only for the canonical final version.
- `images/scene_###.png`.
- `images/image_prompts.json`.
- `images/image_plan.md`.
- `script/spoken_script.md`.
- `production_notes.md`.

Remove:

- `audio/segments*/`, `audio/segment_chunks*/`, raw `audio/narration*.wav` files that are not the retained normalized final audio, copied voice-reference files, and TTS manifests unless explicitly needed for debugging.
- `subtitles/` raw transcript, aligned subtitle, timing, and QC files after the final sidecar SRT has been copied into `video/`.
- `video/render_segments*/`, `video/visual_track*.mp4`, `video/render_concat*.txt`, `video/qc_frames*/`, old alternate final renders, and timeline/debug JSON files not needed for the retained final.
- Copied project-local helper scripts that duplicate bundled `scripts/` functionality.
- `images/contact_sheet.*`, `images/style_guide.md`, and `images/visual_entities.md` unless the user wants a full visual audit trail.

After cleanup, verify the retained files still exist and report the before/after directory size.

## Tool Notes

See `references/toolchain.md` for the current researched tool choices, tradeoffs, and links.
