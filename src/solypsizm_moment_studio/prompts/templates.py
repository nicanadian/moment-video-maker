"""Generators for the four prompt artifacts the artist hands off to ChatGPT and Veo.

Every template here injects the locked brand kit so the artist never retypes
character or aesthetic guidance — that is the core promise of this tool (PRD §11).
"""

from solypsizm_moment_studio.models import BrandKit, Concept, Project, Scene


def _character_block(bk: BrandKit) -> str:
    c = bk.character
    parts = [
        f"- Style: {c.style}",
        f"- Build: {c.build}",
        f"- Skin: {c.skin}",
        f"- Hair: {c.hair}",
        f"- Visor: {c.visor}",
        f"- Jacket: {c.jacket}",
        f"- Shirt: {c.shirt}",
        f"- Pants: {c.pants}",
        f"- Boots: {c.boots}",
    ]
    if c.gloves:
        parts.append(f"- Gloves: {c.gloves}")
    return "\n".join(parts)


def _aesthetic_block(bk: BrandKit) -> str:
    a = bk.aesthetic
    palette = ", ".join(f"{name} {hex_}" for name, hex_ in a.palette.items())
    grade = " ".join(a.color_grade) if a.color_grade else ""
    return f"Palette: {palette}.\nLighting: {a.lighting_cues}\nColor grade: {grade}".strip()


def _song_theme_block(bk: BrandKit, song_slug: str) -> str:
    theme = bk.song_theme(song_slug)
    if theme is None:
        return ""
    return (
        f"Song theme — {theme.title}:\n"
        f"- Mood: {theme.mood}\n"
        f"- Environment: {theme.environment}\n"
        f"- Camera: {theme.camera}\n"
        f"- Character action: {theme.character_action}\n"
        f"- Color accent: {theme.color_accent}\n"
        f"- Pacing: {theme.pacing}"
    )


def brainstorm_prompt(bk: BrandKit, project: Project, lyrics: str, count: int = 5) -> str:
    """ChatGPT brainstorm prompt per PRD §F1.

    Asks for `count` distinct concepts as parseable JSON.
    """
    theme_block = _song_theme_block(bk, project.song_slug)
    return f"""You are helping {bk.artist} brainstorm short-form ("moment") video concepts for the song below.

# Song
Title: {project.song_title}
Artist: {bk.artist}

# Lyrics
{lyrics.strip()}

# Locked character spec (do not change)
{_character_block(bk)}

# Aesthetic
{_aesthetic_block(bk)}

{theme_block}

# Task
Propose {count} DISTINCT concepts for moment videos based on this song. Each concept is a thematic idea (e.g. "abandoned watchtower at dawn") that will be broken into 2-5 scenes later.

For each concept, return a JSON object with these fields:
- "title": short, evocative
- "summary": 1-3 sentences
- "song_themes_referenced": array of short strings from the lyrics or song mood
- "brand_alignment_notes": how the locked character + aesthetic show up in this concept
- "estimated_runtime_seconds": integer, 15-45
- "scene_count": integer, 2-5

Return ONLY a JSON array of {count} concept objects. No prose before or after. No markdown. No code fences.
"""


def scenes_prompt(bk: BrandKit, project: Project, concept: Concept) -> str:
    """ChatGPT scene-breakdown prompt per PRD §F2."""
    theme_block = _song_theme_block(bk, project.song_slug)
    concept_block = (
        f"Concept: {concept.title}\n"
        f"Summary: {concept.summary}\n"
        f"Themes: {', '.join(concept.song_themes_referenced) or '(none)'}\n"
        f"Brand alignment notes: {concept.brand_alignment_notes or '(none)'}\n"
        f"Target runtime: {concept.estimated_runtime_seconds}s\n"
        f"Target scene count: {concept.scene_count}"
    )
    return f"""You are breaking the concept below into {concept.scene_count} scenes for short-form moment videos.

# Locked character spec
{_character_block(bk)}

# Aesthetic
{_aesthetic_block(bk)}

{theme_block}

# Concept
{concept_block}

# Task
Return a JSON array of EXACTLY {concept.scene_count} scene objects. Each scene is a single shot: one start frame, one end frame, one continuous camera motion (Veo 3 takes ~4-6 second clips).

Each scene object must include:
- "title": short
- "description": 1-2 sentences of what happens
- "duration_target_seconds": integer 4-8
- "shot_type": e.g., "wide, locked off, low angle"
- "camera_motion": e.g., "slow dolly-in, 6 seconds"
- "subject_motion": what the character does
- "environment": where this happens, evocatively
- "lighting": how it's lit (mention rim lighting / neon if applicable)
- "mood_tags": 2-4 short tags ("isolation", "approach", "release", etc.)
- "song_section_fit": which section(s) of the song this scene fits ("intro", "verse 1", "pre-chorus", "chorus 1", "bridge", "outro")
- "energy_target": one of "low", "low-mid", "mid", "mid-high", "high"

Return ONLY the JSON array. No prose. No code fences.
"""


def _reference_image_header(bk: BrandKit) -> str:
    """Top-of-prompt instruction: upload the canonical reference image first.

    DALL-E / GPT-image won't lock the cel-shaded character from text alone — the
    reference upload is what holds visor / piping / palette across regenerations
    (review-feedback, editor #2).
    """
    ref = bk.character.reference_image
    if not ref:
        return ""
    return (
        f">>> BEFORE PASTING: upload the reference image at `{ref}` as the seed.\n"
        ">>> The character below MUST match that image exactly. Do not invent new pose or outfit.\n"
    )


def start_frame_prompt(bk: BrandKit, project: Project, scene: Scene) -> str:
    """ChatGPT image start-frame prompt per PRD §F3.

    Inlines the character spec verbatim, leads with the reference-upload
    instruction, and ends with the watermark/text disclaimer.
    """
    theme = bk.song_theme(project.song_slug)
    palette_line = bk.aesthetic.lighting_cues or ""
    base_lines = list(bk.always_include_in_image_prompts) or [
        "vertical 1080x1920 anime-style cel-shaded illustration"
    ]

    header = _reference_image_header(bk)
    parts: list[str] = []
    if header:
        parts.append(header)
    parts.append("Generate a " + base_lines[0] + ".")
    parts.append("")
    parts.append("Character (preserve exactly per the locked spec — match the uploaded reference):")
    parts.append(_character_block(bk))
    parts.append("")
    parts.append(f"Scene: {scene.environment or scene.description}.")
    if theme is not None:
        parts.append(f"Song theme cues: {theme.environment} {theme.color_accent}")
    if scene.shot_type:
        parts.append(f"Camera: {scene.shot_type}.")
    if scene.lighting:
        parts.append(f"Lighting: {scene.lighting}.")
    if palette_line:
        parts.append(f"Mood: {palette_line}")
    parts.append("")
    parts.append("No text in the image. No logos or watermarks.")
    return "\n".join(parts)


def end_frame_prompt(bk: BrandKit, project: Project, scene: Scene) -> str:
    """ChatGPT image end-frame continuation prompt per PRD §F3.

    Re-anchors brand kit aesthetic + song theme so palette/grade don't drift on
    the second generation (review-feedback, editor #7). Asks for significant
    motion with explicit numeric guidelines so the second frame isn't a
    near-duplicate of the first.
    """
    motion = scene.subject_motion or "character has taken at least 4 paces forward"
    camera = scene.camera_motion or "camera has dollied at least 4 meters"
    theme = bk.song_theme(project.song_slug)
    palette_line = bk.aesthetic.lighting_cues or ""

    parts = [
        "Continue from the previous image. Same character, same environment, "
        "same color palette, same grade.",
        "",
        "Change:",
        f"- {camera}",
        f"- {motion}",
        "",
        "Preserve every character design detail exactly per the locked spec "
        "(single horizontal cyan visor strip — NOT goggles; hexagonal jacket "
        "piping — NOT zigzag; pants side-seam piping; combat boots).",
    ]
    if theme is not None:
        parts.append(f"Hold the song theme: {theme.color_accent}; {theme.mood}")
    if palette_line:
        parts.append(f"Hold the mood: {palette_line}")
    parts.append("")
    parts.append("No text. No watermark.")
    return "\n".join(parts)


def veo_motion_prompt(bk: BrandKit, project: Project, scene: Scene) -> str:
    """Veo 3 motion prompt per PRD §F3.

    Restructured per editor feedback (#1): explicit Aspect, Audio (silent —
    Veo 3 dubs music by default which fights the master), Duration, and a
    newline-delimited Avoid: stanza for negatives. Style line drawn from the
    brand kit's veo_prompt.style.
    """
    veo = bk.veo_prompt
    style = ", ".join(veo.style) if veo.style else ", ".join(bk.always_include_in_veo_prompts)
    theme = bk.song_theme(project.song_slug)
    env_extra = f" {theme.color_accent}" if theme is not None else ""
    negatives = bk.negative_prompt_items or [
        "no slow motion",
        "no morphing",
        "no distorted face",
        "no text",
        "no watermark",
    ]
    avoid_block = "\n".join(f"- {n}" for n in negatives)

    return f"""Subject: {bk.character.description_oneliner}
Action: {scene.subject_motion or scene.description}
Environment: {scene.environment}{env_extra}
Lighting: {scene.lighting or bk.aesthetic.lighting_cues}
Camera: {scene.camera_motion or scene.shot_type}
Aspect: {veo.aspect}
Duration: {veo.duration}
Audio: {veo.audio}
Style: {style}

Avoid:
{avoid_block}"""


def scene_prompts_markdown(bk: BrandKit, project: Project, scene: Scene) -> str:
    """The combined scene-NN-prompts.md output written next to the scene JSON."""
    start = start_frame_prompt(bk, project, scene)
    end = end_frame_prompt(bk, project, scene)
    veo = veo_motion_prompt(bk, project, scene)
    return f"""# Prompts — {scene.id}

> Brand kit auto-injected. Paste each block as-is.

## 1. Start frame (ChatGPT image)

```
{start}
```

---

## 2. End frame (ChatGPT image continuation)

> Upload the start frame from step 1 first.

```
{end}
```

---

## 3. Veo 3 motion prompt (Flow Labs)

> Upload start and end frames first.

```
{veo}
```
"""
