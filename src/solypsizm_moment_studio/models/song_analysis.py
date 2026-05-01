from pydantic import BaseModel, ConfigDict


class Section(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    start: float
    end: float
    energy_avg: float = 0.0
    energy_peak: float = 0.0
    vibe: str = ""


class SongAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow")

    audio_file: str
    duration_seconds: float
    tempo_bpm: float
    key: str = ""
    sections: list[Section] = []
    beat_grid_seconds: list[float] = []
    downbeat_seconds: list[float] = []
