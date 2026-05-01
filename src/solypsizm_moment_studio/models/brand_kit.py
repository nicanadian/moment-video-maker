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


class Aesthetic(BaseModel):
    model_config = ConfigDict(extra="allow")

    palette: dict[str, str]
    palette_usage: dict[str, str] = {}
    color_grade: list[str] = []
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


class BrandKit(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: str = Field(alias="$schema_version", default="1.0")
    artist: str = "Solypsizm"
    character: CharacterSpec
    aesthetic: Aesthetic
    negative_prompt_items: list[str] = []
    always_include_in_image_prompts: list[str] = []
    always_include_in_veo_prompts: list[str] = []
    song_themes: dict[str, SongTheme] = {}

    def negative_prompt_string(self) -> str:
        return ", ".join(self.negative_prompt_items)

    def song_theme(self, slug: str) -> SongTheme | None:
        return self.song_themes.get(slug)
