# Solypsizm Moment Studio — Product Requirements Document

**Version:** 0.1 (draft)
**Owner:** Nic
**Status:** Specification — not yet implemented
**Last updated:** 2026-04-27

---

## 1. Problem statement

Producing one short-form Solypsizm "moment" video currently requires a long manual chain of work, scattered across multiple apps with no shared state:

1. Brainstorm scene ideas in ChatGPT, copying lyrics + brand context into the chat each time.
2. Pick a concept, then break it into 3–4 scenes — losing the brainstorm context each chat session.
3. Per scene, iterate on start-frame and end-frame prompts in ChatGPT image gen, often re-typing the same character description and brand cues.
4. Hand-write a Veo motion prompt that connects the two frames.
5. Upload start frame, end frame, and prompt into Google Flow Labs / Veo 3, generate, evaluate, re-roll. Often ping-pong back to ChatGPT to iterate prompts.
6. Save the candidate clip somewhere — usually a Downloads folder with no metadata about which scene it belongs to or how good it was.
7. Repeat for the remaining 3 scenes.
8. Find an interesting section of the song (verse 2, pre-chorus + chorus, etc.) — by ear.
9. Edit clips to roughly match the song section.
10. Aim for 9 distinct moment videos per song, but with no system for tracking which clips have been used in which edits, or what's still missing.

Across 3 songs × 9 moments × 3–4 scenes per moment = roughly 80–100 clips needing to be generated, organized, and edited together into 27 final moment videos. Without a system, the artist's working memory becomes the database — context gets lost between sessions, candidate clips pile up unlabeled, and the same brand prompts get re-typed dozens of times.

**The tool's job:** be the durable project memory and the prompt scaffolding for this workflow. Keep concepts, scenes, prompts, frames, clips, and edits all linked in one project. Let the artist focus only on creative judgment calls, not on retyping or re-organizing.

## 2. Goals

- **One project per song.** All concepts, scenes, prompts, frames, clips, and final moments for a song live in one folder with one source-of-truth state file.
- **Brand kit auto-applied.** Every generated prompt — ChatGPT image, ChatGPT continuation, Veo motion — automatically includes the locked Solypsizm character description and brand styling cues from `brand-kit.json`.
- **Concept-to-edit traceability.** Given a final moment video, the artist can see exactly which concept it came from, which scenes feed it, which takes were chosen, and what prompts produced those takes.
- **Zero context-loss between ChatGPT sessions.** The tool persists the concept, scene breakdown, and per-frame prompts on disk so re-opening ChatGPT tomorrow doesn't restart from zero.
- **Reach 9 moments per song with a clear "what's missing" signal.** At any time, the tool answers: how many moments are done, which clips are used where, which song sections still need coverage.
- **Music-aware edit suggestions.** Given the clip library and the song's structure, suggest 9 distinct edit configurations the artist can review and accept.
- **Hand off rendering to the existing Variant Builder.** This tool produces the *concepts and clip libraries*; the Variant Builder (separate PRD) produces the *finished MP4s*.

## 3. Non-goals

- This is **not** an AI image or video generator. It does not generate frames or clips itself. It writes the prompts, organizes the assets, and drives the human who's running ChatGPT and Veo.
- This is **not** a video editor. Final edit assembly happens in DaVinci Resolve or via the Variant Builder.
- This is **not** a publishing tool. It does not schedule, post, or track social performance.
- It does not target the Modern Musician contest — that contest disqualifies AI-generated visuals. A separate tool ("Performance Clip Studio") is appropriate for that workflow.

## 4. User

Nic, working from a Mac. Comfortable with terminal commands when given exact syntax. The tool should feel like an opinionated CLI assistant, not an IDE.

## 5. Conceptual model

```
Project (one per song)
 ├── Concept          (a thematic idea — "abandoned watchtower at dawn")
 │    └── Scene       (a single shot in that concept — "wide approach")
 │         ├── Start frame prompt (text)
 │         ├── End frame prompt (text)
 │         ├── Veo motion prompt (text)
 │         ├── Frame candidates (PNG files with metadata)
 │         └── Clip takes (MP4 files with rating + notes)
 ├── Song analysis    (sections, energy, beat grid)
 └── Moment           (a final 15–45s edit, made from clips)
```

A project can have multiple concepts. A concept always has 2–5 scenes. A scene can have many candidate frames and many candidate take clips. A moment is an edit specification that draws clips from any scenes in any concepts within the project.

This shape mirrors the artist's described workflow exactly — every distinct phase becomes a first-class object with persistent state.

## 6. End-to-end user flow

The artist works in this sequence per song. The numbered tool commands are described in §9.

1. **Set up the project.** `solypsizm new` against the song's lyrics, audio master, and the shared brand kit. Folder structure created.
2. **Brainstorm concepts.** `solypsizm brainstorm` outputs a ready-to-paste prompt for ChatGPT, including the song lyrics + brand kit + a request for N concept ideas. The artist runs that in ChatGPT, then `solypsizm import-concepts` pastes the response back. Each concept becomes a JSON file.
3. **Pick a concept.** `solypsizm pick-concept <id>` marks one concept as the current focus.
4. **Break it into scenes.** `solypsizm scenes` outputs a ChatGPT prompt asking it to break the concept into 3–4 scenes with action / camera / environment / mood fields filled. Artist runs in ChatGPT, then `solypsizm import-scenes` pastes back. Each scene becomes a JSON file with empty prompt fields ready to fill.
5. **For each scene, generate prompts.** `solypsizm prompts <scene-id>` generates three ready-to-paste prompts written in the format ChatGPT and Veo each prefer: (a) start-frame prompt for ChatGPT image, (b) end-frame continuation prompt for ChatGPT image, (c) Veo 3 motion prompt with the start/end frame placeholders. The brand kit context is auto-injected. The artist runs each in the appropriate tool.
6. **Import frames and clips as they're generated.** `solypsizm import-frame --scene <id> --type start <file>` and `solypsizm import-clip --scene <id> --rating 4 --notes "..." <file>`. The artist drops files in via the CLI; the tool moves them into place and updates the scene's metadata.
7. **Analyze the song.** `solypsizm analyze` runs once per project. Outputs a JSON of song sections (intro, verse 1, pre-chorus, chorus, etc.) with start/end timestamps, average energy, and key character per section.
8. **Generate moment edit suggestions.** `solypsizm suggest-moments` reviews the available clips, the song sections, and the artist's mood-tag annotations on each clip. Outputs 9 edit specifications — each pairing a song section with a sequence of clips chosen for fit and diversity. The artist accepts, rejects, or modifies each.
9. **Render.** Each accepted moment spec is handed off to the Variant Builder, which produces the final MP4.
10. **Iterate.** The dashboard view (`solypsizm status`) shows: 9 moments planned per song, X completed, Y in progress, Z song sections still uncovered. The artist returns to step 5–6 to fill gaps.

## 7. Project folder structure

```
~/solypsizm/
  brand-kit.json                  # shared across all projects
  haze-over-the-horizon/
    project.json                  # main state file
    lyrics.txt
    audio/
      master.wav
      song-analysis.json          # output of `solypsizm analyze`
    concepts/
      concept-01-watchtower.json
      concept-02-empty-highway.json
      concept-03-rooftop.json
    scenes/
      concept-01/
        scene-01-wide-approach.json
        scene-01-prompts.md       # ready-to-paste prompts
        scene-01-frames/
          start-v1.png
          start-v2.png            # multiple candidates
          end-v1.png
          end-v2.png
        scene-01-clips/
          take-01.mp4
          take-02.mp4
          take-03.mp4
        scene-01-notes.md
      concept-01/
        scene-02-...
    moments/
      moment-01.json              # an edit specification
      moment-02.json
      ...
      output/
        moment-01.mp4             # rendered by Variant Builder
        ...
    .state/
      hashes.json                 # idempotency tracking
      log.jsonl                   # operation log
```

## 8. Data schemas

### 8.1 `project.json`

```json
{
  "song_title": "Haze over the Horizon",
  "song_slug": "haze",
  "artist": "Solypsizm",
  "release_date": "2026-01-09",
  "lyrics_file": "lyrics.txt",
  "audio_file": "audio/master.wav",
  "brand_kit_path": "../brand-kit.json",
  "target_moment_count": 9,
  "current_concept": "concept-01-watchtower",
  "concepts": ["concept-01-watchtower", "concept-02-empty-highway"],
  "moments_completed": 0,
  "created_at": "2026-04-27T...",
  "updated_at": "2026-04-27T..."
}
```

### 8.2 `concept-XX.json`

```json
{
  "id": "concept-01-watchtower",
  "title": "Abandoned Watchtower at Dawn",
  "summary": "Avatar approaches and climbs an abandoned watchtower as dawn breaks. Mirrors the song's themes of disappearance, watching, and emerging into a new horizon.",
  "song_themes_referenced": ["disappearance", "watching/being watched", "horizon as transition"],
  "brand_alignment_notes": "Visor self-illuminates in pre-dawn dark. Jacket piping reflects in the watchtower's broken windows.",
  "estimated_runtime_seconds": 22,
  "scene_count": 4,
  "scenes": ["scene-01-wide-approach", "scene-02-tower-base", "scene-03-climb", "scene-04-summit"],
  "status": "in_progress",
  "rating": null,
  "notes": ""
}
```

### 8.3 `scene-XX.json`

```json
{
  "id": "scene-01-wide-approach",
  "concept_id": "concept-01-watchtower",
  "title": "Wide approach to the watchtower",
  "description": "Avatar walks across foggy field toward the distant watchtower silhouette as the dawn glow builds behind it.",
  "duration_target_seconds": 6,
  "shot_type": "wide, locked off, low angle",
  "camera_motion": "slow dolly-in, 6 seconds",
  "subject_motion": "character walks forward at brisk pace, fog swirls around legs",
  "environment": "open foggy field, distant watchtower silhouette, deep purple pre-dawn sky transitioning to amber on horizon",
  "lighting": "horizon backlight, character mostly silhouette, visor self-illuminates cyan",
  "mood_tags": ["isolation", "approach", "anticipation"],
  "song_section_fit": ["verse 1", "intro"],
  "energy_target": "low-mid",
  "prompts": {
    "start_frame": "...",
    "end_frame": "...",
    "veo_motion": "..."
  },
  "frames": {
    "start": [
      { "file": "start-v1.png", "imported_at": "...", "selected": false },
      { "file": "start-v2.png", "imported_at": "...", "selected": true }
    ],
    "end": [
      { "file": "end-v1.png", "imported_at": "...", "selected": true }
    ]
  },
  "clip_takes": [
    {
      "file": "take-01.mp4",
      "imported_at": "...",
      "rating": 3,
      "notes": "good motion but jacket piping flickered between cyan and white",
      "selected": false
    },
    {
      "file": "take-02.mp4",
      "imported_at": "...",
      "rating": 4,
      "notes": "tight. character drift held. fog motion natural",
      "selected": true
    }
  ],
  "status": "complete",
  "created_at": "...",
  "updated_at": "..."
}
```

### 8.4 `song-analysis.json`

```json
{
  "audio_file": "audio/master.wav",
  "duration_seconds": 218.4,
  "tempo_bpm": 92.0,
  "key": "C# minor",
  "sections": [
    { "name": "intro", "start": 0.0, "end": 8.5, "energy_avg": 0.21, "energy_peak": 0.28, "vibe": "ambient build" },
    { "name": "verse 1", "start": 8.5, "end": 26.0, "energy_avg": 0.35, "energy_peak": 0.42, "vibe": "low energy melodic" },
    { "name": "pre-chorus", "start": 26.0, "end": 33.0, "energy_avg": 0.55, "energy_peak": 0.65, "vibe": "rising tension" },
    { "name": "chorus 1", "start": 33.0, "end": 50.0, "energy_avg": 0.78, "energy_peak": 0.92, "vibe": "anthemic release" },
    ...
  ],
  "beat_grid_seconds": [0.0, 0.652, 1.304, ...],
  "downbeat_seconds": [0.0, 2.608, 5.217, ...]
}
```

### 8.5 `moment-XX.json`

A moment is an edit specification compatible with the Variant Builder's `variants.json` format (see Variant Builder PRD §7.2). Adds a `source_song_section` field for traceability:

```json
{
  "id": "moment-01-prechorus-tower",
  "song_slug": "haze",
  "duration_target_seconds": 24,
  "source_song_section": { "name": "pre-chorus → chorus 1", "start": 26.0, "end": 50.0 },
  "edit_strategy": "tension_release",
  "segments": [
    { "type": "title_card", "duration": 1.5, "title": "Haze over the Horizon", "subtitle": "Solypsizm", "footer": "Release Jan 9, 2026" },
    { "type": "clip", "source": "scenes/concept-01/scene-01-clips/take-02.mp4", "audio_offset": 26.0 },
    { "type": "clip", "source": "scenes/concept-01/scene-03-clips/take-01.mp4", "audio_offset": 33.0 },
    { "type": "clip", "source": "scenes/concept-01/scene-04-clips/take-04.mp4", "audio_offset": 41.0 },
    { "type": "end_card", "image": "../shared/end-cards/stream-now.png", "duration": 2.5 }
  ],
  "captions_source": "captions/main.srt",
  "status": "approved",
  "rendered_to": "moments/output/moment-01.mp4"
}
```

## 9. CLI surface

Top-level command: `solypsizm`. Subcommands grouped by workflow stage.

### Project lifecycle

```
solypsizm new <slug> --song-title "..." --lyrics <file> --audio <file>
solypsizm status [<slug>]
solypsizm open <slug>          # cd into project + show summary
```

### Concepts

```
solypsizm brainstorm           # outputs ChatGPT-ready prompt to stdout + clipboard
solypsizm import-concepts <input.txt|->   # parses ChatGPT response back into concept JSONs
solypsizm list-concepts
solypsizm pick-concept <id>
solypsizm rate-concept <id> --rating 4 --notes "..."
```

### Scenes

```
solypsizm scenes                            # ChatGPT prompt for the current concept
solypsizm import-scenes <input.txt|->
solypsizm list-scenes
solypsizm prompts <scene-id>                # outputs all 3 prompts as ready-to-paste markdown
solypsizm prompts <scene-id> --copy         # copies the 3 prompts to clipboard, one at a time
```

### Frames and clips

```
solypsizm import-frame --scene <id> --type {start|end} <file>
solypsizm select-frame --scene <id> --type {start|end} <filename>
solypsizm import-clip --scene <id> --rating 1-5 --notes "..." <file>
solypsizm select-clip --scene <id> <filename>
solypsizm review-clips <scene-id>           # opens scene's clips folder + shows ratings table
```

### Song analysis

```
solypsizm analyze                           # runs librosa-based pipeline on audio/master.wav
solypsizm sections                          # prints sections table
```

### Moments

```
solypsizm suggest-moments [--count 9]       # outputs N moment-XX.json files for review
solypsizm review-moment <id>                # prints the spec, asks accept/reject/edit
solypsizm render-moment <id>                # hands off to Variant Builder
solypsizm render-all                        # render every approved moment
```

### Maintenance

```
solypsizm doctor                            # validates project structure, missing assets, etc.
solypsizm log                               # tail the operation log
```

All commands operate on the current-directory project unless `--project <slug>` is passed.

## 10. Functional requirements per stage

### F1. Concept brainstorming (§9 brainstorm + import-concepts)

The `brainstorm` command produces a single ChatGPT prompt that includes:
- The song title and artist name.
- The full lyrics inline.
- The brand kit's character description and aesthetic spec, summarized.
- A request for N (default 5) distinct concept ideas, each as a JSON-parseable block with title, summary, themes referenced, brand alignment notes, estimated runtime, and a count of scenes (2–5 each).

The response from ChatGPT (a block of JSON or near-JSON) is pasted to stdin of `import-concepts`. The tool tolerates light formatting variation — markdown code fences, leading prose, etc. — and parses out the concepts. Each concept is written to `concepts/concept-NN-<slug>.json`.

If parsing fails, the tool prints the offending block and exits non-zero, preserving the raw input in `.state/last-import.txt` so the artist can fix and retry.

### F2. Scene breakdown (§9 scenes + import-scenes)

Same flow as F1 but the prompt asks ChatGPT to break the *current* concept into 2–5 scenes. The prompt includes the full concept JSON. The output is parsed back into `scenes/concept-NN/scene-NN-<slug>.json` files.

### F3. Per-scene prompt generation (§9 prompts)

Given a scene, the tool produces three ready-to-paste prompts:

**Start-frame prompt** (for ChatGPT image gen):
- Inlines the brand kit's character description verbatim.
- Adds the scene's environment, lighting, shot type, and mood.
- Explicitly disclaims text overlays and watermarks.
- Output ends with "No text in the image. No logos or watermarks."

**End-frame prompt** (for ChatGPT image continuation):
- Refers to "the previous image" as the seed.
- Asks for a continuation that *significantly* moves the camera and/or character (the tool injects a numeric guideline: "character has moved at least 4 paces" or "camera has dollied at least 4 meters").
- Preserves character design.

**Veo 3 motion prompt:**
- Structured into the labeled fields Veo prefers (Subject / Action / Environment / Camera / Style / Lighting / Negative).
- Imports `subject_motion`, `camera_motion`, `environment`, `lighting` from the scene JSON.
- Explicitly populates a Negative Prompt: "no slow motion, no morphing, no distorted face, no text, no watermark."
- References the brand-kit character.

The output is written to `scene-NN-prompts.md` and optionally piped one-at-a-time to the macOS clipboard via `--copy`.

### F4. Frame and clip import (§9 import-frame, import-clip)

Both commands:
- Validate the source file exists and has the expected media type.
- Move (not copy) it into the scene's `-frames/` or `-clips/` subfolder with a normalized filename (e.g., `start-v3.png`, `take-04.mp4`).
- Update the scene JSON's `frames` or `clip_takes` array.
- Compute a hash for idempotency tracking.

For clips, `--rating 1-5` and `--notes "..."` are optional but encouraged. The artist's notes are the primary input for the moment-suggestion algorithm.

### F5. Frame and clip selection (§9 select-frame, select-clip)

Marks one frame as the "selected" start or end frame for a scene, and one clip as the "selected" take. The selected take is what gets used in moment edits.

If the artist hasn't selected, the tool falls back to the highest-rated take. Ties broken by import order.

### F6. Song analysis (§9 analyze)

Runs a librosa-based pipeline on `audio/master.wav`:
- Tempo and beat grid (`librosa.beat.beat_track`).
- Downbeat detection (madmom or beat-grid heuristic).
- Section segmentation (`librosa.segment.agglomerative` on chroma + MFCC features, with empirical thresholds).
- Per-section RMS energy.
- Section labeling — initially heuristic (intro / verse / chorus / bridge / outro by position and energy), with a `--lyrics-aware` mode that aligns lyrics to sections for label hints.

Output: `audio/song-analysis.json` per §8.4.

Quality note: section detection is approximate. The artist can hand-edit `song-analysis.json` to correct labels; the tool respects manual edits unless `analyze --force` is passed.

### F7. Moment suggestions (§9 suggest-moments)

Given the project state, suggest N (default 9) distinct moment edits.

**Algorithm sketch:**

1. Build a clip pool from all scenes' selected takes that have a rating ≥ 3 and at least one mood tag.
2. Build a song-section pool from `song-analysis.json`. Filter to sections suitable for moment cuts (skip pure intro silence, skip outros under 6s, prefer sections with clear energy delta).
3. For each of N target moments:
   - Pick a song section, biasing toward variety (don't repeat the same section twice unless we have to).
   - Pick a sequence of clips matching the section's energy and mood, preferring clips tagged with that section in `song_section_fit`.
   - Aim for 3–4 clips per moment, totaling within ±20% of the section's duration.
   - Diversity constraint: no two moments should share the exact same clip set, and no clip should appear in more than ⌈N/3⌉ moments.
4. Emit `moment-NN.json` files in `moments/`. Each is a Variant Builder–compatible spec with `status: "pending_review"`.

The tool prints a summary table (moment ID, song section, clips used, edit strategy) and exits.

### F8. Moment review and render (§9 review-moment, render-moment)

`review-moment` prints the moment spec in a human-readable layout, plays the moment's audio range from `master.wav` (via `afplay` on macOS), and asks the artist to mark `approved` or `rejected`. Rejected moments stay in the project folder for reference but won't be rendered.

`render-moment` invokes the Variant Builder with the moment's spec as the input, returning the path to the rendered MP4.

### F9. Status dashboard (§9 status)

Prints a one-screen overview per project:

```
Project: haze-over-the-horizon
Concepts: 3 explored (1 in progress)
Scenes: 12 created (8 with selected clips, 4 in progress)
Clips: 31 imported (17 rated ≥ 3)
Song sections: 7 detected (intro, v1, pc1, c1, v2, c2, bridge, outro)
Moments: 9 planned, 5 approved, 2 rendered, 4 pending review
Coverage: chorus 1 (3 moments), verse 2 (1), pre-chorus (2), bridge (0)
GAPS: bridge has 0 moments — needs a clip with high-energy mood tag.
```

Coverage analysis points the artist at the next concrete creative task.

## 11. Brand-kit integration

A single `brand-kit.json` file lives at the top of `~/solypsizm/`. It encodes:
- Character description (the locked Solypsizm avatar spec).
- Aesthetic palette and motion guidelines.
- Always-include negative-prompt items.
- Per-song theme overrides (e.g., Haze = foggy purple horizon, Scatter Brained = rainy cyberpunk city).

Every prompt the tool generates injects the relevant subset of the brand kit. The artist never types the character description by hand.

`brand-kit.json` is the JSON twin of the existing `Solypsizm Brand Kit v1.docx`. A bootstrap utility (`solypsizm bootstrap-brand-kit`) extracts content from the Word doc and produces an editable JSON.

## 12. ChatGPT integration modes

### 12.1 Manual mode (default for v1)

The tool generates prompts as text. Artist pastes into the ChatGPT web app. Result is pasted back into the tool. No API key required, no cost beyond ChatGPT Plus.

### 12.2 API mode (v2 extension)

If `OPENAI_API_KEY` is set in the environment, the tool calls the OpenAI API directly:
- Concept brainstorming uses the chat completions endpoint with the same prompt template.
- Image generation calls `images.generate` (start frame) and `images.edit` (end frame, with start frame uploaded).
- Tool downloads outputs into the scene folder automatically.

API mode dramatically speeds up the loop but adds per-token / per-image cost. Disabled by default; `--api` flag opt-in per command.

## 13. Veo 3 / Flow Labs integration

Flow Labs has no public consumer API as of v1. The tool produces ready-to-paste Veo prompts. The artist runs them in Flow Labs manually. Output MP4s are downloaded to the artist's Downloads folder, then `solypsizm import-clip` moves them into place.

If Google ships a Veo API tier accessible to consumers, a v2 `--api` flag will queue Veo runs directly the same way ChatGPT API mode does. Not in scope for v1.

## 14. Music analysis subsystem

### 14.1 Dependencies

- `librosa` (Python) — beat tracking, segmentation, MFCC, RMS, harmonic features.
- `madmom` — optional, improves downbeat detection.
- `pydub` — audio I/O.

### 14.2 Outputs

`song-analysis.json` per §8.4. Always-deterministic given the same input audio.

### 14.3 Manual override

The artist can edit `song-analysis.json` after running `analyze`. Subsequent `analyze` runs respect manual edits unless `--force` is passed. The tool diff-shows what would change before overwriting.

## 15. Edit-suggestion algorithm details

The algorithm is heuristic, not optimization-based, and tunable via `~/solypsizm/edit-config.json`:

```json
{
  "min_clip_rating": 3,
  "min_clips_per_moment": 3,
  "max_clips_per_moment": 5,
  "moment_duration_target_seconds": 22,
  "moment_duration_tolerance_pct": 20,
  "max_clip_reuse_count": 3,
  "section_diversity_weight": 0.6,
  "mood_match_weight": 0.4,
  "energy_match_weight": 0.5,
  "always_lead_with_hook": true
}
```

Two strategies offered:

- **`tension_release`**: pair a low-energy section with the chorus that follows it. Clip 1 from a low-energy scene, clips 2–3 from a high-energy scene with the energy peak landing on the chorus downbeat.
- **`section_focus`**: stay within one song section. Use 3–4 clips from scenes that share mood tags with that section.

The artist can request specific strategies per moment (`suggest-moments --strategy tension_release --count 5`).

## 16. Technical requirements

### 16.1 Platform

- macOS 14+ on Apple Silicon (primary).
- Linux secondary (for headless runs).
- Tool stack: Python 3.11+, `click` for CLI, `pydantic` for schema validation, `librosa` for audio analysis.

### 16.2 Dependencies

Single install:

```
brew install python@3.11 ffmpeg
pip install solypsizm-moment-studio
```

Optional: `pip install solypsizm-moment-studio[api]` adds OpenAI API support.

### 16.3 Performance targets

- `analyze` on a 4-minute song: ≤ 30s.
- `suggest-moments --count 9`: ≤ 5s.
- `import-clip`: ≤ 1s including hash and metadata write.

## 17. Error handling and validation

- Every state-mutating command writes to `.state/log.jsonl` for traceability.
- Every parsed-from-ChatGPT input is preserved in `.state/last-import.txt` on failure.
- `solypsizm doctor` validates: project schema integrity, file references resolve, brand-kit is locatable, audio file is the expected format.
- Atomic writes: state file changes go to `project.json.tmp` first and rename on success, so a crash mid-write doesn't corrupt the project.

## 18. Success criteria

The tool ships v1 when:

1. The artist can run a song from cold start (`solypsizm new`) to 9 approved moment specs in ≤ 4 hours of human work, with the bulk of generation/iteration time being ChatGPT and Veo wall-clock.
2. Re-opening a project after 48 hours surfaces all in-progress state without confusion. The `status` view tells the artist exactly what to do next.
3. Brand-kit drift goes to zero — every prompt includes the locked character description automatically.
4. The artist can answer "which clip is in which moment" instantly via `solypsizm trace <clip>`.
5. `suggest-moments` produces 9 specs that the artist accepts with minor edits or fewer for at least 70% of suggestions.
6. The handoff to Variant Builder produces a valid MP4 from any approved moment without manual editing of the moment spec.

## 19. Future extensions (v2+)

- **Live ChatGPT API mode** for fully unattended concept and prompt generation.
- **Veo 3 API integration** when Google ships consumer access.
- **Kling integration** as an alternative to Veo, with start/end-frame upload via Kling's API.
- **Visual moment editor** — a Tauri or Electron GUI showing the song waveform with sections, the clip library as cards, and drag-and-drop moment composition.
- **Auto-rating of clips** — use a vision model to compare each take against the scene's start and end frames, flagging character-drift takes automatically.
- **Cross-song clip reuse** — if a clip from Haze fits Scatter Brained's mood, allow it as a candidate, with attribution tracking.
- **Performance dashboard integration** — once moments are posted, ingest TikTok / Reels analytics and feed back into mood-tag scoring (which moods perform best for this artist?).
- **Automatic 3×3 framework** — generate the next 8 moments automatically once the artist locks the first one as a "seed."

## 20. Relationship to the other Solypsizm tools

```
Brand Kit (Word doc)
       │
       ▼
brand-kit.json      ← bootstrapped once
       │
       ▼
Moment Studio       ← THIS PRD
   (concept → scenes → frames → clips → moment specs)
       │
       ▼
Variant Builder     ← rendering pipeline (separate PRD)
   (moment specs + clip files → finished MP4s)
       │
       ▼
Posting workflow    ← out of scope (manual or future tool)
```

The three tools are independently shippable but share data shapes. A change to brand-kit.json propagates downstream automatically.

## 21. Open questions for Nic

1. **ChatGPT prompt format.** Do you want me to mirror the structure of prompts you've already been using successfully, or invent a new one? If the former, paste me 2–3 of your best ChatGPT brainstorm prompts and I'll reverse-engineer the template.
2. **Where does the tool live — your Mac, this Cowork session, or both?** If it's local, you install once and run anywhere. If it's session-bound, I run it for you on demand. Both is also possible (the same Python package in both places).
3. **State file format — JSON or SQLite?** v1 spec is JSON for simplicity and version-control-friendliness. SQLite would be better at scale but feels overbuilt for 3–10 active projects. Confirm.
4. **Concept count default.** I've defaulted to 5 concepts per song. You may want fewer if you typically pick a direction quickly, or more if you like to explore. What's your real number?
5. **Clip rating scale.** I've used 1–5. You may want 👎 / 🤷 / 👍 / ⭐ — pick your scale.
6. **Mood tag taxonomy.** Right now the tool accepts free-form mood tags ("isolation", "approach", "anticipation"). v1 should probably converge on a controlled vocabulary so the suggestion algorithm has cleaner inputs. Want me to propose a 20–30 tag list?
7. **What counts as "approved"?** Auto-approve any moment with all four 3-Move tests passing? Always require human approval? v1 default: human approval required.
8. **Lyrics format.** Plain text, LRC with timestamps, or both? Some features (lyric-aware section detection) need timestamps; others don't.
9. **Should v1 include the bootstrap from your Word doc**, or assume `brand-kit.json` is hand-written?
10. **Build sequence.** I see four reasonable v0 builds, in increasing scope:
    - **(a)** Just the prompt-generation half (no analysis, no suggestions). 1 day.
    - **(b)** + song analysis and clip library. 2 days.
    - **(c)** + suggestion algorithm. 3 days.
    - **(d)** Full v1. 4–5 days.
    Which scope do you want first?

---

## Appendix A — Example session (target user experience)

```
$ cd ~/solypsizm
$ solypsizm new haze --song-title "Haze over the Horizon" --lyrics ./haze-lyrics.txt --audio ./haze-master.wav
✓ Created project at ~/solypsizm/haze-over-the-horizon

$ solypsizm brainstorm
Generated ChatGPT prompt (1432 tokens). Copied to clipboard.

[paste in ChatGPT, get response, copy it back]

$ pbpaste | solypsizm import-concepts -
✓ Imported 5 concepts. Run 'solypsizm list-concepts' to review.

$ solypsizm list-concepts
[1] Abandoned Watchtower at Dawn
[2] Empty Highway with Headlights
[3] Rooftop in the Fog
[4] Mirror Hallway
[5] Subway Platform After Hours

$ solypsizm pick-concept concept-01-watchtower
$ solypsizm scenes
[ChatGPT prompt copied to clipboard]

[paste, response, paste back]

$ pbpaste | solypsizm import-scenes -
✓ Imported 4 scenes for concept-01-watchtower.

$ solypsizm prompts scene-01-wide-approach --copy
[Prompt 1 of 3 copied — ChatGPT start frame]
[press Enter to copy next]
[Prompt 2 of 3 copied — ChatGPT end frame continuation]
[press Enter to copy next]
[Prompt 3 of 3 copied — Veo 3 motion prompt]

[generate frames, generate clip]

$ solypsizm import-frame --scene scene-01-wide-approach --type start ~/Downloads/dalle-1.png
✓ Imported as start-v1.png

$ solypsizm import-clip --scene scene-01-wide-approach --rating 4 --notes "tight, character drift held" ~/Downloads/veo-output-2.mp4
✓ Imported as take-01.mp4

[repeat for all 12 scenes across 3 concepts]

$ solypsizm analyze
✓ Detected 7 sections, BPM 92, key C# minor.

$ solypsizm suggest-moments --count 9
✓ Generated 9 moment specs in moments/. Run 'solypsizm review-moment moment-01-...' to start.

$ solypsizm review-moment moment-01-prechorus-tower
[plays audio, prints spec]
> approve

$ solypsizm render-all
[renders 9 MP4s via Variant Builder]
✓ 9/9 moments rendered. See moments/output/.

$ solypsizm status
Moments: 9 planned, 9 approved, 9 rendered. ✓ Done.
```

## Appendix B — Build effort estimate

- Scope (a) prompt-generation only: 1 day for working draft.
- Scope (b) + song analysis + clip library: 2 days.
- Scope (c) + suggestion algorithm: 3 days.
- Scope (d) full v1: 4–5 days.

Recommended path: build (a) and (b) inside this Cowork session as a Python package in your folder; run against the Haze song; iterate; then layer (c) once the data is real and the suggestion algorithm has actual clips to operate on.
