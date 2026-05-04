# v2: Multi-provider API mode + benchmark harness + auto-pipeline

**Status:** draft (planning)
**Owner:** Nic
**Started:** 2026-05-04
**Predecessor:** `docs/projects/02-phase-d-hardening.md` (v1 ships first)
**Source PRD:** `ref-docs/Solypsizm Moment Studio - PRD.md` §12.2 (API mode), §13 (Veo), §19 (future extensions)

## Why this exists

v1 is a paste-back workflow: the artist runs ChatGPT and Flow Labs by hand, the tool keeps state. v2 collapses the manual loop. Three layered ambitions, sequential:

1. **Wire 3+ providers** behind a uniform interface (E).
2. **Benchmark them head-to-head** on Solypsizm-specific work to pick winners by quality + speed + cost (F).
3. **Run the full pipeline unattended** — song + lyrics in, 9 reviewable moments out, with confidence-gated review steps (G).

The big v2 unlock is **Veo 3 via the Gemini API** — that's literally the manual Flow Labs step today. Imagen 4 + gpt-image-1 give us two image-gen ecosystems to pit against each other. OpenRouter gives multi-model text breadth from one key.

## Locked decisions (per Nic)

| # | Question | Locked answer |
|---|---|---|
| 1 | Auth strategy | OpenAI via `openai` CLI's OAuth login (token cached at `~/.openai/auth.json`, refresh handled by SDK). Gemini + OpenRouter via API key. |
| 2 | Budget cap | **$40/day hard cap.** Refuse new generations when daily spend ≥ cap; warn at 80%. |
| 3 | VLM judge model | Gemini 2.5 Flash (cheap, vision-strong, good enough). Sub-benchmark may switch this. |
| 4 | Cache scope | Per-project: `~/solypsizm/<slug>/.cache/api/`. Avoids cross-song bleed; reruns of same prompt + ref hit. |
| 5 | Reference-image support | Required for image-gen providers in benchmarks. Text-only image providers naturally penalize themselves on character-fidelity scoring. |
| 6 | Priority order | E first, then **minimal-G with sensible defaults landing alongside F** (so we get value before benchmarks finish). |
| 7 | Confidence-gate threshold | Defaults locked from F's benchmark data, not pre-set. |

## Provider matrix

| Modality | OpenAI (OAuth) | Gemini (key) | OpenRouter (key) |
|---|---|---|---|
| Text / concepts | GPT-5, GPT-4.1 | Gemini 2.5 Pro / Flash | All of the above + Claude Opus 4.7, Gemini, DeepSeek V3, Llama 4 |
| Image gen | gpt-image-1, DALL-E 3 | Imagen 4, Imagen 3 | Flux Pro, SDXL, gpt-image passthrough |
| Video gen | Sora (limited API) | **Veo 3** (key unlock — replaces manual Flow Labs) | Thin: occasional Kling / Runway via fal-style routing |

## Phasing

### Phase E — Provider abstraction (~2-3 days build)

Goal: any command that today emits a paste-back prompt can instead invoke a provider directly.

**Deliverables:**

1. `solypsizm_moment_studio/providers/` package with three protocols:
   - `TextProvider.complete(system, user, **kwargs) → CompletionResult`
   - `ImageProvider.generate(prompt, reference=None, **kwargs) → ImageResult`
   - `VideoProvider.generate(prompt, start_frame, end_frame, **kwargs) → VideoResult`
   - All results carry `cost_usd`, `latency_ms`, `model_id`, `raw_response`.
2. Adapters: `OpenAIAdapter`, `GeminiAdapter`, `OpenRouterAdapter`. Each registers what modalities + models it offers.
3. **Secrets layer** (`secrets.py`):
   - Read order: env vars → `~/.solypsizm/credentials.json` (chmod 600, gitignored).
   - `solypsizm secrets login openai` shells out to the openai CLI OAuth flow.
   - `solypsizm secrets set gemini` / `set openrouter` prompts and stores.
   - `solypsizm secrets status` shows what's configured without printing values.
4. **Cost tracker** (`cost.py`):
   - Pricing table per `(provider, model)` in `pricing.json`. Update quarterly; PRs welcome.
   - `BudgetGuard` checks daily total against the cap before each call. Persists to `~/solypsizm/.budget/<YYYY-MM-DD>.json`.
   - `solypsizm budget` shows today's spend, remaining cap, monthly total, top-N by model.
5. **Idempotent cache** (`cache.py`):
   - Key: SHA-256 of `(provider, model, prompt, params, reference_hash)`.
   - Stored at `<project>/.cache/api/<hash>.{json,png,mp4}`.
   - `solypsizm cache prune --older-than 30d` to clean up.
   - Cache hits don't count against the daily budget.
6. **`--api` flag** wired into existing commands:
   - `solypsizm brainstorm --api` runs text gen directly, writes concepts.
   - `solypsizm scenes --api` same for scene breakdown.
   - `solypsizm prompts <scene> --api` generates start + end frames + Veo clip directly, imports them into the scene.
   - All keep their paste-back behavior as default; `--api` is purely additive.

**Implementation notes:**

- Lazy import every provider SDK so a missing `google-genai` install doesn't break the OpenAI path.
- `TextProvider`, `ImageProvider`, `VideoProvider` are `typing.Protocol`s — no inheritance gymnastics, just structural typing.
- All async-capable providers should also offer a sync wrapper. Phase E uses sync; Phase G goes async.
- Failure modes (rate limit, network blip, content policy block) raise typed exceptions: `ProviderRateLimited`, `ProviderRefused`, `ProviderUnavailable`. Callers handle.

### Phase F — Benchmark harness (~2 days build)

Goal: pick a default model per modality based on Solypsizm-specific quality + cost.

**Deliverables:**

1. **`solypsizm benchmark <prompt-set>`** command:
   ```
   solypsizm benchmark image-keyframe \
     --providers openai,gemini,openrouter \
     --models openai/gpt-image-1,gemini/imagen-4,openrouter/flux-pro \
     --judge gemini/gemini-2.5-flash \
     --takes 3 \
     --budget 5
   ```
2. **Prompt sets** in `benchmarks/prompt-sets/`:
   - `image-keyframe.md` — canonical Solypsizm scene (e.g. watchtower at dawn, full character spec, song theme cues).
   - `video-motion.md` — canonical motion prompt with start + end frames (uses winners from image-keyframe).
3. **Run output** at `benchmarks/<YYYY-MM-DD-HHMMSS>/`:
   - `manifest.json` — config, providers, models, total cost, total latency, run UUID.
   - `<provider>__<model>__take-NN.{png,mp4}` — the raw artifacts.
   - `judge_scores.json` — VLM judge output per artifact.
   - `report.md` — human-readable leaderboard.
4. **VLM judge** (`judge.py`):
   - Loads the brand kit + the canonical reference PNG + the generated artifact + the original prompt.
   - Asks Gemini 2.5 Flash to score on 4 dimensions (0-10 each):
     - Character fidelity (visor strip, jacket piping correct) — **40% weight**
     - Prompt fidelity (scene matches what was asked) — 25%
     - Aesthetic match (cel-shaded, palette, mood) — 25%
     - Quality (composition, no artifacts) — 10%
   - Returns scored JSON + a one-line justification per artifact.
5. **Leaderboard report**: ranks each `(provider, model)` by weighted score; columns for `score / cost / latency / cost-per-quality-point`. Picks a default per modality (highest cost-per-quality at usable score).

**Implementation notes:**

- The judge itself needs validation. Sub-benchmark: have the judge re-score a known-good Solypsizm reference and a known-bad one (e.g. a Sora generic anime); confirm scores diverge as expected.
- Benchmark runs MUST hit the cache layer — if a benchmark is re-run with the same prompt set + models, it should be free. New takes only happen with `--seed-different` or `--rerun`.
- Cost cap (`--budget 5`) is per-run; the daily cap is independent.

### Phase G — Auto-pipeline (~3-5 days build)

Goal: `solypsizm auto haze --moments 9` produces 9 reviewable moments unattended.

**Deliverables:**

1. **`solypsizm auto <slug>`** command:
   ```
   solypsizm auto haze \
     --moments 9 \
     --review-gates concept,final \
     --auto-approve-threshold 32 \
     --budget 30
   ```
   `--review-gates` lists the stages that pause for human input. Default: `concept,final`. To go fully autonomous: `--review-gates none`.
2. **State machine** in `auto.py`:
   ```
   pre-flight (doctor --global)
     → concept brainstorm (text gen, 1 call)
     → [GATE: concept] human picks or auto-pick highest-scored
     → scene breakdown (text gen, 1 call)
     → per-scene start frame (image gen, N takes, score, pick best)
     → per-scene end frame (image gen, N takes, score, pick best)
     → per-scene motion (video gen, N takes, score, pick best)
     → analyze song
     → suggest moments
     → [GATE: final] human approves/rejects each
     → handoff to Variant Builder (still v2-or-later)
   ```
3. **Async job queue** persisted to `.state/jobs.jsonl`:
   - Each job: `{id, kind, status, provider, model, prompt_hash, started_at, finished_at, result_path}`.
   - Long-running ops (video gen ~60-90s) submitted, polled in background.
   - **`solypsizm auto resume <slug>`** picks up where it left off — survives Ctrl+C, network drops, daily-cap pauses.
4. **Confidence gates**:
   - Each generated artifact gets a judge score.
   - Score ≥ `--auto-approve-threshold` (default 32 / 40 = 80%) → auto-pick.
   - Below threshold → log to `.state/auto-review-queue.jsonl` for human triage; `solypsizm auto review <slug>` walks the queue.
5. **Budget interlock**:
   - Pre-flight estimates total cost from the benchmark winners' average per-call cost × number of expected calls.
   - Refuses to start if estimate > `--budget`.
   - Pauses (resumable) if daily $40 cap is hit mid-run.
6. **Threshold calibration**:
   - First-run default: 32/40, conservative.
   - After each run, log human override rate (how often the artist overruled the auto-pick).
   - `solypsizm auto calibrate` analyzes override history and suggests new threshold.

**Implementation notes:**

- The pipeline writes the same artifacts as the manual workflow (concept JSONs, scene JSONs, frame PNGs, clip MP4s, moment JSONs). Manual mode and auto mode are interoperable — start manual, finish auto, or vice versa.
- `--review-gates` accepts: `concept`, `scenes`, `frames`, `clips`, `final`, or `none`. Comma-separated.
- A failed step doesn't tank the run; it's marked failed in the queue and moves on. The artist can re-run failed jobs only via `auto resume --retry-failed`.
- Watermark / safety / content-policy refusals from any provider become judge-zero artifacts and feed back to the threshold.

### Phase H — Variant Builder integration

Out of scope. Lives in the Variant Builder repo per PRD §20. v2 prepares the spec, doesn't render.

## Cost model (rough)

Per-moment cost estimate using F's benchmark winners (TBD; placeholder pricing):

| Step | Calls | $/call | Subtotal |
|---|---|---|---|
| Concept brainstorm (text) | 1 | $0.05 | $0.05 |
| Scene breakdown (text) | 1 | $0.05 | $0.05 |
| Start frames (3 takes × 4 scenes) | 12 | $0.04-0.20 | $0.50-2.40 |
| End frames (3 takes × 4 scenes) | 12 | $0.04-0.20 | $0.50-2.40 |
| Motion clips (2 takes × 4 scenes) | 8 | $0.30-0.50 | $2.40-4.00 |
| Judge scoring | 32 | $0.001 | $0.05 |
| **Per moment** | | | **$3.55-9.00** |
| **Per 9-moment song** | | | **$32-81** |

This **could exceed the $40/day cap** on the higher end. Mitigations:
- Cache hits across reruns (huge — most retries hit cache).
- Reduce takes from 3 to 2 once a winning model is identified.
- Cap takes per scene to 1 in auto mode after threshold confidence is high.

## Testing strategy

- **Provider adapters**: record/replay fixtures using `vcrpy` so unit tests don't actually call APIs. One real-call integration test gated behind `RUN_PROVIDER_TESTS=1`.
- **Cost tracker**: pure pricing-table math, easy to unit test.
- **Cache**: round-trip + invalidation tests.
- **Judge**: fixture-based — known-good / known-bad images, assert scores in expected ranges.
- **Auto-pipeline**: state-machine unit tests with mocked providers; end-to-end smoke gated behind `RUN_AUTO_TESTS=1`.

## Open questions for Nic to revisit later

1. **OpenAI Sora API access** — full availability is uncertain as of v1. If Sora is open-tier by the time we hit Phase F, add it to the video benchmark. Otherwise Veo 3 is the default.
2. **Imagen 4 vs gpt-image-1 reference-image support** — they have different APIs (file upload vs base64). The adapter layer normalizes, but reference-fidelity may differ. Phase F will tell us.
3. **Self-hosted alternative** — Flux via Replicate / Fal / locally is cheaper at scale but adds operational complexity. Defer until v2.5+ if API costs stay reasonable.
4. **Per-song budget vs global daily** — current plan: $40/day across all songs. If working 3 songs in parallel, could need song-scoped budgets.
5. **VLM judge calibration drift** — Gemini Flash updates may change scoring distribution. Consider pinning a specific Flash version for reproducibility, or re-baselining quarterly.
6. **Style consistency across providers** — running the same scene through gpt-image-1 vs Imagen 4 will produce visually different cel-shading. Auto-pipeline should pin one model per scene to avoid Frankenstein moments.
7. **Veo 3 audio direction** — the v1 prompt says `Audio: silent video, no music`. Veo 3 via Gemini API: confirm the prompt actually disables audio gen. If not, separate `audio_track=none` API param needed.
8. **Storage growth** — generated artifacts at 768x1344 PNG (~1MB) × 24 takes × 9 moments × N songs adds up. Consider compressing or pruning losing takes after benchmarks lock in winners.

## Risks

| Risk | Mitigation |
|---|---|
| Daily $40 cap blocks a planned run | Auto-pipeline pauses cleanly and resumes the next day; cache means resume re-spends only on uncached calls. |
| Benchmark judge is itself biased toward one model family | Run a sub-benchmark of the judges (Gemini Flash vs GPT-4o vs Claude Opus 4.7) on known-good/bad references; pick whichever shows tightest score variance. |
| OpenAI OAuth token expires mid-overnight pipeline | SDK handles refresh; if refresh fails, pipeline pauses with a clear "rerun `solypsizm secrets login openai`" message. |
| Veo 3 generates audio anyway despite prompt | Strip audio in post via ffmpeg before importing the clip — one ffmpeg call. Track as a "must do" in the import path. |
| Provider deprecates a model mid-run | Pricing table updated quarterly; auto-pipeline checks model availability at pre-flight and falls back. |
| Spec drift between paste-back and `--api` outputs | Same JSON shapes either way — `--api` writes the same `concept-NN.json` / `scene-NN.json` / `take-NN.mp4`. Tests assert this. |
| Budget cap hit silently mid-`auto` run | UI shows running daily total in the auto-pipeline progress display; logs note when cap stops a job. |

## Success criteria for v2

1. `solypsizm secrets login openai && solypsizm secrets set gemini && solypsizm secrets set openrouter` configures all three providers.
2. `solypsizm doctor --global` passes with all three credentials green.
3. `solypsizm benchmark image-keyframe --budget 5` produces a leaderboard with at least 3 (provider, model) candidates ranked by Solypsizm-fidelity.
4. `solypsizm prompts <scene> --api` generates start + end + motion artifacts directly into the project, identical-shaped to manual mode.
5. `solypsizm auto haze --moments 9 --budget 30` produces 9 moment specs in a single overnight run, ≥70% of which Nic accepts (matching v1's PRD §18 #5 criterion at automated scale).
6. Daily $40 cap is respected; pipeline resumes cleanly after pauses.
7. Cache means re-running the same `auto` invocation costs $0 (all hits).

## Out of scope for v2

- **Variant Builder integration** (still its own tool; out per PRD §20).
- **Self-hosted models** (Flux/SDXL on local GPU; defer to v2.5+).
- **Cross-song clip reuse** (PRD §19).
- **Performance dashboard ingestion** (PRD §19).
- **Lyric-aware section detection** (PRD §F6 deferred — possibly fits v2 if the API mode makes it cheap).
- **Auto-rating of clips against keyframes** (PRD §19 — judge layer almost gives this for free, leave as v2.5).

## Suggested build sequence

Phase E first (foundation). Then F and minimal-G land in parallel:
- F validates which models to use as defaults.
- Minimal-G means `solypsizm auto haze` works using a single hand-picked default per modality (gpt-image-1, Veo 3) before benchmarks finish — gives Nic an immediate win.
- Once F's leaderboard is in, defaults switch to whatever won.
- Full-G (confidence calibration, threshold tuning) is iterative against real-song data.

Estimated total: ~7-10 build days end-to-end, plus benchmark wallclock + iteration on confidence gates.
