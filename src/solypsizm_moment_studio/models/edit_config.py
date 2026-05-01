from pydantic import BaseModel, ConfigDict


class EditConfig(BaseModel):
    """Per-PRD §15. Shared across projects, lives at ~/solypsizm/edit-config.json."""

    model_config = ConfigDict(extra="allow")

    min_clip_rating: int = 3
    min_clips_per_moment: int = 3
    max_clips_per_moment: int = 5
    moment_duration_target_seconds: float = 22.0
    moment_duration_tolerance_pct: float = 20.0
    max_clip_reuse_count: int = 3
    section_diversity_weight: float = 0.6
    mood_match_weight: float = 0.4
    energy_match_weight: float = 0.5
    always_lead_with_hook: bool = True
