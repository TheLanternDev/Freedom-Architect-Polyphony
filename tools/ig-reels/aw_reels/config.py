from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # tools/ig-reels
REPO_ROOT = ROOT.parent.parent  # architekt-wolnosci/
BRAND_DIR = ROOT / "brand"
OUTPUT_DIR = ROOT / "output"
REPO_ENV = REPO_ROOT / ".env"
# Klucz ElevenLabs — domyślnie ~/Desktop/.env (nadpisz AW_ELEVENLABS_ENV)
ELEVENLABS_ENV = Path(os.getenv("AW_ELEVENLABS_ENV", str(Path.home() / "Desktop" / ".env")))
# Domyślny głos: Brian — Deep, Resonant and Comforting (eleven_multilingual_v2,
# mroczny spokojny narrator Syeza); nadpisz ELEVENLABS_VOICE_ID w .env
DEFAULT_ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"
DEFAULT_ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"


@dataclass(frozen=True)
class IgDefaults:
    aspect_ratio: str
    resolution: str
    duration: int
    model: str


@dataclass(frozen=True)
class BrandStyle:
    name: str
    tagline: str
    prompt_suffix: str
    ig_defaults: IgDefaults
    visual_language: tuple[str, ...]
    audio_direction: tuple[str, ...]
    brand_motifs: dict[str, str]  # identity-key -> fragment obrazu (tożsamość AW)
    signature_suffix: str  # dosypywane gdy koncept ma signature: true


def load_env() -> None:
    # Główny .env repo ma pierwszeństwo (XAI_API_KEY) — bez kopiowania klucza do tools/
    load_dotenv(REPO_ENV, override=False)
    load_dotenv(ROOT / ".env", override=False)
    if ELEVENLABS_ENV.is_file():
        load_dotenv(ELEVENLABS_ENV, override=False)
    root_env = os.getenv("AW_ROOT_ENV")
    if root_env:
        load_dotenv(root_env, override=False)


def get_api_key() -> str:
    load_env()
    key = os.getenv("XAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Brak XAI_API_KEY. Ustaw w tools/ig-reels/.env lub w głównym .env repo."
        )
    return key


def get_elevenlabs_api_key() -> str:
    load_env()
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Brak ELEVENLABS_API_KEY. Ustaw w ~/Desktop/.env lub AW_ELEVENLABS_ENV."
        )
    return key


def get_elevenlabs_voice_id() -> str:
    load_env()
    return os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID).strip()


def get_elevenlabs_model_id() -> str:
    load_env()
    return os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_ELEVENLABS_MODEL_ID).strip()


def load_brand_style() -> BrandStyle:
    data = yaml.safe_load((BRAND_DIR / "style.yaml").read_text(encoding="utf-8"))
    ig = data["ig_defaults"]
    return BrandStyle(
        name=data["name"],
        tagline=data["tagline"],
        prompt_suffix=data["prompt_suffix"].strip(),
        ig_defaults=IgDefaults(
            aspect_ratio=ig["aspect_ratio"],
            resolution=ig["resolution"],
            duration=int(ig["duration"]),
            model=ig["model"],
        ),
        visual_language=tuple(data["visual_language"]),
        audio_direction=tuple(data["audio_direction"]),
        brand_motifs={
            k: str(v).strip() for k, v in (data.get("brand_motifs") or {}).items()
        },
        signature_suffix=str(data.get("signature_suffix", "")).strip(),
    )


def load_concepts_data() -> dict:
    return yaml.safe_load((BRAND_DIR / "concepts.yaml").read_text(encoding="utf-8"))


def load_concepts() -> dict[str, dict]:
    return load_concepts_data().get("concepts", {})


def load_agents_canon() -> dict[str, dict]:
    return load_concepts_data().get("agents_canon", {})


def get_default_concept() -> str:
    data = load_concepts_data()
    policy = data.get("policy") or {}
    explicit = str(policy.get("default_concept", "")).strip()
    if explicit:
        return explicit
    for cid, concept in (data.get("concepts") or {}).items():
        if concept.get("default"):
            return cid
    concepts = load_concepts()
    if not concepts:
        raise RuntimeError("Brak konceptów w brand/concepts.yaml")
    return next(iter(sorted(concepts)))
