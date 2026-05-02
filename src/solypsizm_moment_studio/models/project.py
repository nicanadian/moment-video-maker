from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    model_config = ConfigDict(extra="allow")

    song_title: str
    song_slug: str
    artist: str = "Solypsizm"
    release_date: str | None = None
    lyrics_file: str = "lyrics.txt"
    audio_file: str = "audio/master.wav"
    brand_kit_path: str = "../brand-kit.json"
    target_moment_count: int = 9
    current_concept: str | None = None
    current_scene: str | None = None
    concepts: list[str] = Field(default_factory=list)
    moments_completed: int = 0
    created_at: str
    updated_at: str
