from __future__ import annotations

from dataclasses import dataclass

from .config import BrandStyle, load_concepts


@dataclass(frozen=True)
class CompiledPrompt:
    text: str
    hook: str
    title: str


def _identity_fragment(c: dict, style: BrandStyle) -> str | None:
    """Zwraca motyw tożsamości AW dla pola `identity` koncepta (jeden na reel).

    To jest warstwa rozumowania marki: zamiast wklejać Aksjomaty/Radę/Fragment
    ręcznie do każdej sceny, koncept deklaruje JEDEN klucz, a kompilator dosypuje
    pasujący fragment z `style.brand_motifs`. Egzekwuje różnicowanie — jeden reel,
    jeden element tożsamości.
    """
    key = (c.get("identity") or "").strip()
    if not key:
        return None
    frag = style.brand_motifs.get(key)
    if frag is None:
        raise KeyError(
            f"Koncept odwołuje się do identity='{key}', którego brak w "
            f"style.yaml: brand_motifs. Dostępne: {', '.join(sorted(style.brand_motifs))}"
        )
    return frag


def compile_concept_prompt(concept_id: str, style: BrandStyle) -> CompiledPrompt:
    concepts = load_concepts()
    if concept_id not in concepts:
        available = ", ".join(sorted(concepts))
        raise KeyError(f"Nieznany koncept '{concept_id}'. Dostępne: {available}")

    c = concepts[concept_id]
    parts: list[str] = [c["scene"].strip()]

    # Warstwa tożsamości: dokładnie jeden element marki (Rada / Syez / Fragment /
    # Aksjomat / Szow / logo). Wstrzykiwany jako jawna dyrektywa, nie jako napis.
    identity = _identity_fragment(c, style)
    if identity:
        parts.append(identity)

    parts.append(f"Audio: {c.get('audio', 'ambient cinematic')}.")

    # Sygnatura logo tylko gdy koncept ją zamawia (np. intro/outro sting).
    if c.get("signature") and style.signature_suffix:
        parts.append(style.signature_suffix)

    parts.append(style.prompt_suffix)

    return CompiledPrompt(
        text="\n\n".join(parts),
        hook=c.get("hook", ""),
        title=c.get("title", concept_id),
    )


def compile_raw_prompt(text: str, *, style: BrandStyle, with_brand: bool = True) -> CompiledPrompt:
    body = text.strip()
    if with_brand:
        body = f"{body}\n\n{style.prompt_suffix}"
    return CompiledPrompt(text=body, hook="", title="custom")


def compile_custom_prompt(
    scene: str,
    *,
    audio: str = "ambient cinematic score",
    style: BrandStyle,
) -> CompiledPrompt:
    parts = [
        scene.strip(),
        f"Audio: {audio}.",
        style.prompt_suffix,
    ]
    return CompiledPrompt(text="\n\n".join(parts), hook="", title="custom")


def mutation_variants(base_prompt: str, count: int = 3) -> list[str]:
    """Delikatne warianty promptu do równoległej selekcji."""
    lenses = [
        "Emphasize the symbolic identity element more strongly; keep it abstract, no text.",
        "Emphasize stronger gold rim lighting and more atmospheric fog.",
        "Emphasize tighter framing and intimate scale, macro architectural details.",
        "Emphasize wider epic scale, crane shot revealing vast space.",
        "Emphasize teal accent lights and cooler shadow contrast.",
    ]
    return [f"{base_prompt}\n\nVariation: {lenses[i % len(lenses)]}" for i in range(count)]


def edit_prompt_suggestions() -> list[str]:
    """Typowe instrukcje edit-video dla iteracji."""
    return [
        "Increase golden rim lighting intensity on main subject, keep everything else identical.",
        "Slow down camera movement by 30%, preserve scene composition.",
        "Add subtle atmospheric fog and floating dust particles in light beams.",
        "Make shadows deeper and richer navy, preserve gold highlights.",
        "Reduce visual clutter — simplify background, keep focal subject.",
        "Enhance teal accent glow on secondary elements only.",
        "Make the mood more contemplative and still — less motion in scene.",
    ]
