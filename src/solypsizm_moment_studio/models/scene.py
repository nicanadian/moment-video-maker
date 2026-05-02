from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SceneStatus = Literal["draft", "prompts_ready", "frames_imported", "clips_imported", "complete"]


class FramePrompts(BaseModel):
    model_config = ConfigDict(extra="allow")

    start_frame: str = ""
    end_frame: str = ""
    veo_motion: str = ""


class Frame(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: str
    imported_at: str
    selected: bool = False
    hash: str = ""


class ClipTake(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: str
    imported_at: str
    rating: int | None = None
    notes: str = ""
    selected: bool = False
    hash: str = ""


class Scene(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    concept_id: str
    title: str
    description: str = ""
    duration_target_seconds: int = 6
    shot_type: str = ""
    camera_motion: str = ""
    subject_motion: str = ""
    environment: str = ""
    lighting: str = ""
    mood_tags: list[str] = Field(default_factory=list)
    song_section_fit: list[str] = Field(default_factory=list)
    energy_target: str = "low-mid"
    prompts: FramePrompts = Field(default_factory=FramePrompts)
    frames: dict[str, list[Frame]] = Field(default_factory=lambda: {"start": [], "end": []})
    clip_takes: list[ClipTake] = Field(default_factory=list)
    status: SceneStatus = "draft"
    created_at: str
    updated_at: str
