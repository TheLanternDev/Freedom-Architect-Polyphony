#!/usr/bin/env python3
"""Znajdź i przetestuj kandydatów na głos ElevenLabs dla agenta SZOW (Agent Cienia).

Użycie:
    export ELEVENLABS_API_KEY=...
    python tools/find_szow_voice.py              # ranking + generowanie próbek
    python tools/find_szow_voice.py --dry-run    # tylko ranking (bez API TTS)
    python tools/find_szow_voice.py --force      # nadpisz istniejące MP3
    python tools/find_szow_voice.py --max-candidates 5

Decyzję o wyborze głosu podejmuje człowiek po przesłuchaniu — skrypt nie wybiera zwycięzcy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API_BASE = "https://api.elevenlabs.io/v1"
MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"

SZOW_SAMPLE_TEXT = (
    "Nazywam się Szow. Agent Cienia. Ten, którego chcieliście pogrzebać. "
    "Spękany. Wypalony. Niezniszczalny. Twoja decyzja."
)

VOICE_SETTINGS: dict[str, Any] = {
    "stability": 0.42,
    "similarity_boost": 0.90,
    "style": 0.60,
    "use_speaker_boost": True,
    "speed": 0.90,
}

LIBRARY_SEARCH_TERMS = (
    "raspy",
    "deep",
    "gravelly",
    "dark",
    "villain",
    "narrator",
    "intense",
    "smoky",
)

POSITIVE_KEYWORDS: dict[str, int] = {
    "deep": 3,
    "low": 2,
    "raspy": 4,
    "gravelly": 4,
    "gritty": 3,
    "smoky": 3,
    "dark": 3,
    "intense": 2,
    "menacing": 3,
    "villain": 3,
    "narrator": 2,
    "authoritative": 2,
    "mature": 2,
    "middle_aged": 2,
    "middle aged": 2,
    "old": 2,
    "cracked": 2,
    "rough": 2,
    "hoarse": 3,
    "brooding": 2,
    "ominous": 3,
    "sinister": 3,
    "dramatic": 1,
    "heavy": 2,
    "gravel": 3,
    "husky": 2,
}

NEGATIVE_KEYWORDS: dict[str, int] = {
    "bright": -3,
    "warm": -2,
    "friendly": -3,
    "young": -2,
    "cheerful": -3,
    "upbeat": -3,
    "energetic": -2,
    "soft": -2,
    "gentle": -2,
    "coaching": -3,
    "child": -4,
    "kid": -4,
    "teen": -2,
    "sweet": -2,
    "pleasant": -2,
    "casual": -1,
    "high": -2,
    "higher": -2,
    "light": -1,
    "youthful": -2,
    "excited": -2,
    "happy": -2,
}

FEMALE_GENDER_TOKENS = frozenset({"female", "f", "woman", "feminine"})
BRIGHT_AGE_TOKENS = frozenset({"young", "child", "kid", "teen", "teenager"})

OUTPUT_DIR = Path(__file__).resolve().parent / "szow_voice_candidates"
MAX_LIBRARY_PAGES = 20
REQUEST_TIMEOUT_S = 120
MAX_RETRIES = 5
BACKOFF_BASE_S = 1.5


@dataclass
class VoiceCandidate:
    voice_id: str
    name: str
    source: str  # account | library
    gender: str = ""
    age: str = ""
    descriptive: str = ""
    use_case: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    description: str = ""
    public_owner_id: str | None = None
    preview_url: str | None = None
    is_added_by_user: bool | None = None
    free_users_allowed: bool | None = None
    score: int = 0
    score_reasons: list[str] = field(default_factory=list)
    generation_note: str = ""

    def label_blob(self) -> str:
        parts = [
            self.name,
            self.gender,
            self.age,
            self.descriptive,
            self.use_case,
            self.description,
            *self.labels.values(),
        ]
        return " ".join(str(p).lower() for p in parts if p)

    def labels_summary(self) -> str:
        bits = []
        if self.gender:
            bits.append(f"gender={self.gender}")
        if self.age:
            bits.append(f"age={self.age}")
        if self.descriptive:
            bits.append(f"descriptive={self.descriptive}")
        if self.use_case:
            bits.append(f"use_case={self.use_case}")
        for key in sorted(self.labels):
            if key not in {"gender", "age", "descriptive", "use_case"}:
                bits.append(f"{key}={self.labels[key]}")
        if self.description:
            bits.append(f"desc={self.description[:120]}")
        return "; ".join(bits) if bits else "—"

    def library_url(self) -> str:
        return f"https://elevenlabs.io/app/voice-library?voiceId={self.voice_id}"


class ElevenLabsClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _headers(self, *, accept_audio: bool = False, json_body: bool = False) -> dict[str, str]:
        headers = {"xi-api-key": self._api_key}
        if json_body:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
        elif accept_audio:
            headers["Accept"] = "audio/mpeg"
        else:
            headers["Accept"] = "application/json"
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        accept_audio: bool = False,
        allow_status: frozenset[int] | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        url = API_BASE + path
        if query:
            clean = {k: v for k, v in query.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean, doseq=True)

        data: bytes | None = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=self._headers(accept_audio=accept_audio, json_body=body is not None),
        )

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                    status = resp.status
                    payload = resp.read()
                    resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                    return status, payload, resp_headers
            except urllib.error.HTTPError as exc:
                status = exc.code
                payload = exc.read()
                resp_headers = {k.lower(): v for k, v in exc.headers.items()}
                if allow_status and status in allow_status:
                    return status, payload, resp_headers
                if status in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                    retry_after = resp_headers.get("retry-after")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else BACKOFF_BASE_S * (2**attempt)
                    print(f"  [HTTP {status}] ponawiam za {wait:.1f}s…", file=sys.stderr)
                    time.sleep(wait)
                    last_error = exc
                    continue
                return status, payload, resp_headers
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_BASE_S * (2**attempt)
                    print(f"  [sieć] {exc.reason}; ponawiam za {wait:.1f}s…", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Błąd połączenia z ElevenLabs: {exc.reason}") from exc

        raise RuntimeError(f"ElevenLabs: przekroczono liczbę ponowień ({last_error})")

    @staticmethod
    def json_or_text(payload: bytes) -> Any:
        if not payload:
            return None
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            return payload.decode("utf-8", errors="replace")


def _normalize_gender(raw: str) -> str:
    return raw.strip().lower()


def _is_female(candidate: VoiceCandidate) -> bool:
    gender = _normalize_gender(candidate.gender or candidate.labels.get("gender", ""))
    if gender in FEMALE_GENDER_TOKENS:
        return True
    blob = candidate.label_blob()
    return any(tok in blob.split() for tok in ("female", "woman", "feminine"))


def _is_bright_or_high(candidate: VoiceCandidate) -> bool:
    blob = candidate.label_blob()
    age = (candidate.age or candidate.labels.get("age", "")).strip().lower()
    if age in BRIGHT_AGE_TOKENS:
        positives = sum(1 for kw in ("deep", "raspy", "gravelly", "dark", "villain", "smoky") if kw in blob)
        if positives < 1:
            return True
    bright_markers = ("bright", "high-pitched", "high pitched", "cheerful", "warm", "friendly", "youthful")
    if any(m in blob for m in bright_markers):
        dark_markers = ("deep", "raspy", "gravelly", "dark", "villain", "smoky", "menacing", "ominous")
        if not any(m in blob for m in dark_markers):
            return True
    return False


def score_candidate(candidate: VoiceCandidate) -> None:
    blob = candidate.label_blob()
    score = 0
    reasons: list[str] = []

    for keyword, weight in POSITIVE_KEYWORDS.items():
        if keyword in blob:
            score += weight
            reasons.append(f"+{weight} {keyword}")

    for keyword, weight in NEGATIVE_KEYWORDS.items():
        if keyword in blob:
            score += weight
            reasons.append(f"{weight} {keyword}")

    if candidate.source == "account":
        score += 1
        reasons.append("+1 własny głos na koncie")

    if candidate.is_added_by_user:
        score += 1
        reasons.append("+1 już dodany na koncie")

    candidate.score = score
    candidate.score_reasons = reasons


def passes_filter(candidate: VoiceCandidate) -> tuple[bool, str]:
    if _is_female(candidate):
        return False, "odrzucono: głos żeński"
    if _is_bright_or_high(candidate):
        return False, "odrzucono: zbyt jasny/wysoki/młody profil"
    return True, ""


def voice_from_account(raw: dict[str, Any]) -> VoiceCandidate:
    labels = raw.get("labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    return VoiceCandidate(
        voice_id=str(raw.get("voice_id", "")),
        name=str(raw.get("name", "")),
        source="account",
        gender=str(labels.get("gender", "")),
        age=str(labels.get("age", "")),
        descriptive=str(labels.get("descriptive", labels.get("description", ""))),
        use_case=str(labels.get("use_case", "")),
        labels={str(k): str(v) for k, v in labels.items()},
        description=str(raw.get("description") or ""),
        preview_url=raw.get("preview_url"),
        is_added_by_user=True,
    )


def voice_from_library(raw: dict[str, Any]) -> VoiceCandidate:
    return VoiceCandidate(
        voice_id=str(raw.get("voice_id", "")),
        name=str(raw.get("name", "")),
        source="library",
        gender=str(raw.get("gender", "")),
        age=str(raw.get("age", "")),
        descriptive=str(raw.get("descriptive", "")),
        use_case=str(raw.get("use_case", "")),
        description=str(raw.get("description") or ""),
        public_owner_id=str(raw.get("public_owner_id", "")) or None,
        preview_url=raw.get("preview_url"),
        is_added_by_user=bool(raw.get("is_added_by_user")) if raw.get("is_added_by_user") is not None else None,
        free_users_allowed=bool(raw.get("free_users_allowed")) if raw.get("free_users_allowed") is not None else None,
    )


def merge_candidate(existing: VoiceCandidate, incoming: VoiceCandidate) -> VoiceCandidate:
    if incoming.source == "library" and incoming.public_owner_id:
        existing.public_owner_id = incoming.public_owner_id
        existing.preview_url = incoming.preview_url or existing.preview_url
        existing.free_users_allowed = incoming.free_users_allowed
        if incoming.is_added_by_user is not None:
            existing.is_added_by_user = incoming.is_added_by_user
    for field_name in ("gender", "age", "descriptive", "use_case", "description"):
        if not getattr(existing, field_name) and getattr(incoming, field_name):
            setattr(existing, field_name, getattr(incoming, field_name))
    existing.labels.update(incoming.labels)
    return existing


def fetch_account_voices(client: ElevenLabsClient) -> list[VoiceCandidate]:
    print("Pobieram głosy własne (GET /v1/voices)…")
    status, payload, _ = client.request("GET", "/voices")
    if status >= 400:
        detail = client.json_or_text(payload)
        raise RuntimeError(f"GET /voices → HTTP {status}: {detail}")
    data = client.json_or_text(payload)
    voices = data.get("voices", []) if isinstance(data, dict) else []
    result = []
    for raw in voices:
        if not isinstance(raw, dict):
            continue
        vid = str(raw.get("voice_id", "")).strip()
        if not vid:
            continue
        result.append(voice_from_account(raw))
    print(f"  → {len(result)} głosów na koncie")
    return result


def fetch_library_voices(client: ElevenLabsClient) -> list[VoiceCandidate]:
    print("Przeszukuję Voice Library (GET /v1/shared-voices)…")
    seen_pages: set[tuple[str, int]] = set()
    result: list[VoiceCandidate] = []

    for term in LIBRARY_SEARCH_TERMS:
        page = 0
        while page < MAX_LIBRARY_PAGES:
            query = {
                "page_size": 100,
                "page": page,
                "gender": "male",
                "search": term,
            }
            status, payload, _ = client.request("GET", "/shared-voices", query=query)
            if status >= 400:
                detail = client.json_or_text(payload)
                print(f"  [ostrzeżenie] search={term!r} page={page} → HTTP {status}: {detail}", file=sys.stderr)
                break
            data = client.json_or_text(payload)
            if not isinstance(data, dict):
                break
            voices = data.get("voices") or []
            print(f"  search={term!r} page={page} → {len(voices)} wyników")
            for raw in voices:
                if not isinstance(raw, dict):
                    continue
                vid = str(raw.get("voice_id", "")).strip()
                if not vid:
                    continue
                result.append(voice_from_library(raw))
            page_key = (term, page)
            if page_key in seen_pages:
                break
            seen_pages.add(page_key)
            if not data.get("has_more"):
                break
            page += 1

    print(f"  → {len(result)} surowych trafień z biblioteki (przed deduplikacją)")
    return result


def collect_candidates(client: ElevenLabsClient) -> dict[str, VoiceCandidate]:
    pool: dict[str, VoiceCandidate] = {}
    for candidate in fetch_account_voices(client) + fetch_library_voices(client):
        if not candidate.voice_id:
            continue
        if candidate.voice_id in pool:
            merge_candidate(pool[candidate.voice_id], candidate)
        else:
            pool[candidate.voice_id] = candidate
    return pool


def rank_candidates(pool: dict[str, VoiceCandidate], max_candidates: int) -> list[VoiceCandidate]:
    filtered: list[VoiceCandidate] = []
    rejected = 0
    for candidate in pool.values():
        ok, reason = passes_filter(candidate)
        if not ok:
            rejected += 1
            continue
        score_candidate(candidate)
        filtered.append(candidate)

    filtered.sort(key=lambda c: (-c.score, c.name.lower()))
    top = filtered[:max_candidates]
    print(f"\nPo filtrze: {len(filtered)} pasujących, odrzucono {rejected}. Top {len(top)}:\n")
    for i, c in enumerate(top, start=1):
        reasons = ", ".join(c.score_reasons[:8]) or "brak dopasowań słów kluczowych"
        print(f"  {i:2d}. [{c.score:3d}] {c.name} ({c.voice_id[:12]}…) — {c.source}")
        print(f"      {c.labels_summary()}")
        print(f"      uzasadnienie: {reasons}")
    return top


def _error_message(payload: bytes) -> str:
    try:
        data = json.loads(payload.decode("utf-8"))
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, dict):
                return str(detail.get("message") or detail)
            return str(detail or data)
    except json.JSONDecodeError:
        pass
    text = payload.decode("utf-8", errors="replace").strip()
    return text[:300] if text else "nieznany błąd"


def add_shared_voice(client: ElevenLabsClient, candidate: VoiceCandidate) -> str | None:
    if not candidate.public_owner_id:
        return None
    path = f"/voices/add/{urllib.parse.quote(candidate.public_owner_id)}/{urllib.parse.quote(candidate.voice_id)}"
    body = {"new_name": f"SZOW-candidate-{candidate.name[:40]}", "bookmarked": False}
    status, payload, _ = client.request("POST", path, body=body, allow_status=frozenset({400, 401, 402, 403, 404, 422, 429}))
    if status == 200:
        data = client.json_or_text(payload)
        if isinstance(data, dict) and data.get("voice_id"):
            return str(data["voice_id"])
        return candidate.voice_id
    msg = _error_message(payload)
    candidate.generation_note = f"add shared voice HTTP {status}: {msg}"
    print(f"  [add] HTTP {status} — {msg}", file=sys.stderr)
    return None


def download_preview_url(client: ElevenLabsClient, candidate: VoiceCandidate) -> bytes | None:
    """Fallback: oficjalny podgląd z Voice Library (nie polski tekst Szowa)."""
    url = candidate.preview_url
    if not url:
        return None
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            data = resp.read()
            if data:
                candidate.generation_note = (
                    "fallback: preview_url z biblioteki (nie polski tekst Szowa)"
                )
                return data
    except urllib.error.URLError as exc:
        candidate.generation_note = f"preview_url nieosiągalny: {exc.reason}"
    return None


def synthesize_szow_sample(client: ElevenLabsClient, voice_id: str) -> tuple[bytes | None, str]:
    query = {"output_format": OUTPUT_FORMAT}
    body = {
        "text": SZOW_SAMPLE_TEXT,
        "model_id": MODEL_ID,
        "language_code": "pl",
        "voice_settings": VOICE_SETTINGS,
    }
    path = f"/text-to-speech/{urllib.parse.quote(voice_id)}"
    status, payload, headers = client.request(
        "POST",
        path,
        query=query,
        body=body,
        accept_audio=True,
        allow_status=frozenset({400, 401, 402, 403, 404, 422, 429}),
    )
    if status == 200:
        content_type = headers.get("content-type", "")
        if payload and (payload[:3] == b"ID3" or payload[:2] == b"\xff\xfb" or "audio" in content_type or "mpeg" in content_type):
            return payload, "TTS polski tekst Szowa"
        return None, f"TTS HTTP 200 ale nieprawidłowa treść ({content_type})"
    return None, f"TTS HTTP {status}: {_error_message(payload)}"


def generate_sample(client: ElevenLabsClient, candidate: VoiceCandidate) -> bytes | None:
    voice_id = candidate.voice_id

    audio, note = synthesize_szow_sample(client, voice_id)
    if audio:
        candidate.generation_note = note
        return audio

    if candidate.source == "library" or candidate.public_owner_id:
        added_id = add_shared_voice(client, candidate)
        if added_id:
            audio, note = synthesize_szow_sample(client, added_id)
            if audio:
                candidate.generation_note = f"dodano do konta → {note}"
                return audio

        preview = download_preview_url(client, candidate)
        if preview:
            return preview

    if not candidate.generation_note:
        candidate.generation_note = note
    print(f"  [pominięto] {candidate.name}: {candidate.generation_note}", file=sys.stderr)
    return None


def safe_slug(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:40] or "voice"


def mp3_path(rank: int, candidate: VoiceCandidate) -> Path:
    return OUTPUT_DIR / f"{rank:02d}_{safe_slug(candidate.name)}_{candidate.voice_id}.mp3"


def write_manifest(candidates: list[VoiceCandidate]) -> None:
    lines = [
        "# SZOW — kandydaci głosu ElevenLabs",
        "",
        f"Model: `{MODEL_ID}` | Tekst próbki: polski monolog Szowa",
        "",
        "Przesłuchaj pliki MP3, oceń 1–5 w kolumnie poniżej, wpisz notatki.",
        "Wybrany `voice_id` przenieś do konfiguracji (np. `tools/ig-reels/brand/agent_voices.yaml`).",
        "",
        "| Rank | Nazwa | voice_id | Labels / opis | Voice Library | Ocena 1–5 | Notatki | Status generacji |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, c in enumerate(candidates, start=1):
        lib_link = f"[link]({c.library_url()})" if c.source == "library" or c.public_owner_id else "—"
        lines.append(
            "| {rank} | {name} | `{vid}` | {labels} | {lib} | [ ] |  | {status} |".format(
                rank=i,
                name=c.name.replace("|", "\\|"),
                vid=c.voice_id,
                labels=c.labels_summary().replace("|", "\\|"),
                lib=lib_link,
                status=c.generation_note or "—",
            )
        )
    lines.extend(["", "## Uzasadnienie scoringu (top kandydaci)", ""])
    for i, c in enumerate(candidates, start=1):
        reasons = "; ".join(c.score_reasons) or "brak"
        lines.append(f"{i}. **{c.name}** (score={c.score}): {reasons}")
    lines.append("")
    manifest = OUTPUT_DIR / "manifest.md"
    manifest.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nZapisano manifest: {manifest}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Znajdź i przetestuj głosy ElevenLabs dla agenta SZOW.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=8,
        metavar="N",
        help="Maksymalna liczba kandydatów do próbkowania (domyślnie 8)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Nadpisz już wygenerowane pliki MP3",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tylko ranking — bez generowania audio (oszczędza kredyty)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("Błąd: ustaw zmienną środowiskową ELEVENLABS_API_KEY.", file=sys.stderr)
        return 1
    if args.max_candidates < 1:
        print("Błąd: --max-candidates musi być >= 1.", file=sys.stderr)
        return 1

    client = ElevenLabsClient(api_key)
    pool = collect_candidates(client)
    if not pool:
        print("Brak kandydatów z API.", file=sys.stderr)
        return 1

    top = rank_candidates(pool, args.max_candidates)
    if not top:
        print("Po filtrach nie zostało żadnych kandydatów.", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        write_manifest(top)
        print("\n[--dry-run] Pominięto generowanie audio.")
        _print_final_instructions()
        return 0

    print(f"\nGeneruję próbki → {OUTPUT_DIR}/\n")
    for i, candidate in enumerate(top, start=1):
        dest = mp3_path(i, candidate)
        if dest.exists() and not args.force:
            candidate.generation_note = "pominięto (plik istnieje; użyj --force)"
            print(f"  {i}. {candidate.name} — istnieje {dest.name}")
            continue
        print(f"  {i}. {candidate.name} ({candidate.voice_id[:12]}…)…")
        audio = generate_sample(client, candidate)
        if audio:
            dest.write_bytes(audio)
            print(f"     zapisano {dest.name} — {candidate.generation_note}")
        else:
            print(f"     brak audio — {candidate.generation_note}")

    write_manifest(top)
    _print_final_instructions()
    return 0


def _print_final_instructions() -> None:
    print(
        "\n"
        "── Następny krok ──\n"
        "Przesłuchaj pliki w tools/szow_voice_candidates/, wpisz oceny 1–5 w manifest.md,\n"
        "a wybrany voice_id wpisz do config (np. tools/ig-reels/brand/agent_voices.yaml → agents.Szow)."
    )


if __name__ == "__main__":
    sys.exit(main())
