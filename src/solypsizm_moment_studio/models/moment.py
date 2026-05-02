from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MomentStatus = Literal["pending_review", "approved", "rejected", "rendered"]


class SourceSongSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    start: float
    end: float


class Segment(BaseModel):
    """One element of a moment's edit timeline.

    Variant Builder is the strict consumer; we keep this permissive so future
    segment types don't need a model bump.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["title_card", "clip", "end_card"]
    duration: float | None = None
    title: str | None = None
    subtitle: str | None = None
    footer: str | None = None
    source: str | None = None
    audio_offset: float | None = None
    # Slice of a clip to use, in seconds from the clip file's start. Veo
    # outputs ~8s; the editor needs to know which slice.
    in_point: float | None = None
    out_point: float | None = None
    image: str | None = None


class Moment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    song_slug: str
    duration_target_seconds: float
    source_song_section: SourceSongSection
    edit_strategy: str = "section_focus"
    segments: list[Segment] = Field(default_factory=list)
    captions_source: str | None = None
    status: MomentStatus = "pending_review"
    rendered_to: str | None = None
    created_at: str
    updated_at: str
