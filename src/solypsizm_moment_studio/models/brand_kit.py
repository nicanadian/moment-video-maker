from pydantic import BaseModel, ConfigDict, Field


class CharacterSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    style: str
    build: str
    skin: str
    hair: str
    visor: str
    jacket: str
    shirt: str
    belt: str = ""
    pants: str
    boots: str
    gloves: str = ""
    description_oneliner: str
    # Path to the canonical reference PNG, relative to the brand-kit.json file.
    reference_image: str = ""
    # Optional dict of named pose references (front, back, walking-side, etc.).
    reference_images: dict[str, str] = Field(default_factory=dict)


class Aesthetic(BaseModel):
    model_config = ConfigDict(extra="allow")

    palette: dict[str, str]
    palette_usage: dict[str, str] = Field(default_factory=dict)
    color_grade: list[str] = Field(default_factory=list)
    lighting_cues: str = ""


class SongTheme(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    mood: str
    environment: str
    camera: str
    character_action: str
    color_accent: str
    pacing: str
    reference_video: str = ""


class VeoPromptConstants(BaseModel):
    model_config = ConfigDict(extra="allow")

    aspect: str = "vertical 9:16, 1080x1920"
    duration: str = "~6 seconds, continuous take, locked framing, no cuts"
    audio: str = "silent video — no music, no dialogue, no foley, no SFX"
    style: list[str] = Field(default_factory=list)


class BrandKit(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: str = Field(alias="$schema_version", default="1.0")
    artist: str = "Solypsizm"
    character: CharacterSpec
    aesthetic: Aesthetic
    negative_prompt_items: list[str] = Field(default_factory=list)
    always_include_in_image_prompts: list[str] = Field(default_factory=list)
    always_include_in_veo_prompts: list[str] = Field(default_factory=list)
    veo_prompt: VeoPromptConstants = Field(default_factory=VeoPromptConstants)
    song_themes: dict[str, SongTheme] = Field(default_factory=dict)

    def negative_prompt_string(self) -> str:
        return ", ".join(self.negative_prompt_items)

    def song_theme(self, slug: str) -> SongTheme | None:
        return self.song_themes.get(slug)
