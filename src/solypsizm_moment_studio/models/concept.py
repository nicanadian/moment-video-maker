from typing import Literal

from pydantic import BaseModel, ConfigDict

ConceptStatus = Literal["draft", "in_progress", "complete", "abandoned"]


class Concept(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    summary: str
    song_themes_referenced: list[str] = []
    brand_alignment_notes: str = ""
    estimated_runtime_seconds: int = 22
    scene_count: int = 4
    scenes: list[str] = []
    status: ConceptStatus = "draft"
    rating: int | None = None
    notes: str = ""
