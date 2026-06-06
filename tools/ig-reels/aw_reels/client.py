from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
from pathlib import Path
from typing import Callable

import httpx
import xai_sdk
import grpc
from xai_sdk.video import VideoGenerationError

from .config import OUTPUT_DIR, get_api_key
from . import prompt_cache


ProgressFn = Callable[[str], None]


def _noop(msg: str) -> None:
    pass


def _wrap_api_error(exc: BaseException) -> RuntimeError:
    if isinstance(exc, VideoGenerationError):
        return RuntimeError(f"[{exc.code}] {exc.message}")
    if isinstance(exc, grpc.RpcError):
        code = exc.code().name if exc.code() else "RPC"
        details = exc.details() or str(exc)
        if code == "PERMISSION_DENIED" and "credit" in details.lower():
            return RuntimeError(
                "Brak kredytów xAI lub limit miesięczny wyczerpany.\n"
                "  → https://console.x.ai/ — doładuj konto lub podnieś limit\n"
                f"  ({details})"
            )
        return RuntimeError(f"[{code}] {details}")
    if isinstance(exc, TimeoutError):
        return RuntimeError("Timeout generacji wideo (>20 min)")
    return RuntimeError(str(exc))


def resolve_video_source(video_url: str | None, local_path: str | None) -> str:
    """URL xAI wygasa — do edit używaj lokalnego MP4 jako data URL."""
    if local_path:
        p = Path(local_path)
        if p.is_file() and p.stat().st_size > 0:
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            return f"data:video/mp4;base64,{b64}"
    if video_url:
        return video_url
    raise RuntimeError("Brak wideo — uruchom: aw-reels fetch SESSION ITER")


class VideoClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or get_api_key()
        self._client = xai_sdk.Client(api_key=self._api_key)
        # UWAGA: klienta async NIE tworzymy tutaj. Stub gRPC przypina się do pętli
        # zdarzeń aktywnej przy konstrukcji. `generate_variants` używa asyncio.run()
        # (nowa pętla), więc klient async musi powstać WEWNĄTRZ tej pętli — inaczej
        # "Future attached to a different loop". Tworzony leniwie w generate_batch_async().

    @staticmethod
    def image_path_to_data_url(path: Path) -> str:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def generate_text_to_video(
        self,
        prompt: str,
        *,
        duration: int,
        aspect_ratio: str,
        resolution: str,
        reference_image_paths: list[Path] | None = None,
        on_progress: ProgressFn = _noop,
        use_cache: bool = True,
    ) -> dict:
        cache_key = prompt_cache.cache_key_generate(
            prompt, resolution=resolution, duration=duration, aspect_ratio=aspect_ratio,
        )
        if use_cache:
            hit = prompt_cache.lookup(cache_key)
            if hit:
                on_progress("[cache hit] skipping API call")
                return {
                    "url": hit["video_url"],
                    "duration": duration,
                    "request_id": None,
                    "cached": True,
                    "local_path": hit.get("local_path"),
                    "cache_key": cache_key,
                }

        ref_urls: list[str] | None = None
        if reference_image_paths:
            ref_urls = [self.image_path_to_data_url(p) for p in reference_image_paths]

        on_progress("Generuję text-to-video…")
        try:
            response = self._client.video.generate(
                prompt=prompt,
                model="grok-imagine-video",
                duration=duration,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                reference_image_urls=ref_urls,
                timeout=timedelta(minutes=20),
                interval=timedelta(seconds=5),
            )
        except (VideoGenerationError, grpc.RpcError, TimeoutError) as e:
            raise _wrap_api_error(e) from e

        result = {
            "url": response.url,
            "duration": getattr(response, "duration", duration),
            "request_id": getattr(response, "request_id", None),
            "cached": False,
            "cache_key": cache_key,
        }
        if use_cache:
            prompt_cache.store(cache_key, video_url=result["url"])
        return result

    def edit_video(
        self,
        prompt: str,
        video_url: str,
        *,
        on_progress: ProgressFn = _noop,
        use_cache: bool = True,
    ) -> dict:
        cache_key = prompt_cache.cache_key_edit(prompt, video_url)
        if use_cache:
            hit = prompt_cache.lookup(cache_key)
            if hit:
                on_progress("[cache hit] skipping API call")
                return {
                    "url": hit["video_url"],
                    "duration": None,
                    "request_id": None,
                    "cached": True,
                    "local_path": hit.get("local_path"),
                    "cache_key": cache_key,
                }

        on_progress("Edytuję wideo (edit-video)…")
        try:
            response = self._client.video.generate(
                prompt=prompt,
                model="grok-imagine-video",
                video_url=video_url,
                timeout=timedelta(minutes=20),
                interval=timedelta(seconds=5),
            )
        except (VideoGenerationError, grpc.RpcError, TimeoutError) as e:
            raise _wrap_api_error(e) from e

        result = {
            "url": response.url,
            "duration": getattr(response, "duration", None),
            "request_id": getattr(response, "request_id", None),
            "cached": False,
            "cache_key": cache_key,
        }
        if use_cache:
            prompt_cache.store(cache_key, video_url=result["url"])
        return result

    def extend_video(
        self,
        prompt: str,
        video_url: str,
        *,
        duration: int = 6,
        on_progress: ProgressFn = _noop,
        use_cache: bool = True,
    ) -> dict:
        """Kontynuacja wideo od końca klipu (1–10 s segmentu)."""
        cache_key = prompt_cache.cache_key_edit(
            f"extend:{duration}:{prompt}", video_url,
        )
        if use_cache:
            hit = prompt_cache.lookup(cache_key)
            if hit:
                on_progress("[cache hit] skipping API call")
                return {
                    "url": hit["video_url"],
                    "duration": duration,
                    "request_id": None,
                    "cached": True,
                    "local_path": hit.get("local_path"),
                    "cache_key": cache_key,
                }

        on_progress(f"Przedłużam wideo (+{duration}s)…")
        try:
            response = self._client.video.extend(
                prompt=prompt,
                model="grok-imagine-video",
                video_url=video_url,
                duration=min(max(duration, 1), 10),
                timeout=timedelta(minutes=20),
                interval=timedelta(seconds=5),
            )
        except (VideoGenerationError, grpc.RpcError, TimeoutError) as e:
            raise _wrap_api_error(e) from e

        result = {
            "url": response.url,
            "duration": getattr(response, "duration", duration),
            "request_id": getattr(response, "request_id", None),
            "cached": False,
            "cache_key": cache_key,
        }
        if use_cache:
            prompt_cache.store(cache_key, video_url=result["url"])
        return result

    async def generate_batch_async(
        self,
        prompts: list[str],
        *,
        duration: int,
        aspect_ratio: str,
        resolution: str,
        use_cache: bool = True,
    ) -> list[dict]:
        # Klient async tworzony tu = w pętli uruchomionej przez asyncio.run(),
        # więc kanał gRPC przypina się do właściwej pętli (fix cross-loop Future).
        aclient = xai_sdk.AsyncClient(api_key=self._api_key)

        async def one(prompt: str) -> dict:
            cache_key = prompt_cache.cache_key_generate(
                prompt, resolution=resolution, duration=duration, aspect_ratio=aspect_ratio,
            )
            if use_cache:
                hit = prompt_cache.lookup(cache_key)
                if hit:
                    return {
                        "url": hit["video_url"],
                        "duration": duration,
                        "error": None,
                        "cached": True,
                        "local_path": hit.get("local_path"),
                        "cache_key": cache_key,
                    }
            try:
                response = await aclient.video.generate(
                    prompt=prompt,
                    model="grok-imagine-video",
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    timeout=timedelta(minutes=20),
                    interval=timedelta(seconds=5),
                )
                result = {
                    "url": response.url,
                    "duration": getattr(response, "duration", duration),
                    "error": None,
                    "cached": False,
                    "cache_key": cache_key,
                }
                if use_cache:
                    prompt_cache.store(cache_key, video_url=result["url"])
                return result
            except (VideoGenerationError, grpc.RpcError, TimeoutError) as e:
                err = _wrap_api_error(e)
                return {"url": None, "duration": None, "error": str(err)}

        return await asyncio.gather(*[one(p) for p in prompts])

    def generate_variants(
        self,
        prompts: list[str],
        *,
        duration: int,
        aspect_ratio: str,
        resolution: str,
        on_progress: ProgressFn = _noop,
        use_cache: bool = True,
    ) -> list[dict]:
        on_progress(f"Generuję {len(prompts)} wariantów równolegle…")
        return asyncio.run(
            self.generate_batch_async(
                prompts,
                duration=duration,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                use_cache=use_cache,
            )
        )

    async def edit_batch_async(
        self,
        edits: list[tuple[str, str]],
        *,
        use_cache: bool = True,
    ) -> list[dict]:
        """edits: lista (prompt, source_video_url)"""
        # Klient async w pętli asyncio.run() (fix cross-loop Future), jak w batch.
        aclient = xai_sdk.AsyncClient(api_key=self._api_key)

        async def one(prompt: str, video_url: str) -> dict:
            cache_key = prompt_cache.cache_key_edit(prompt, video_url)
            if use_cache:
                hit = prompt_cache.lookup(cache_key)
                if hit:
                    return {
                        "url": hit["video_url"],
                        "duration": None,
                        "error": None,
                        "cached": True,
                        "local_path": hit.get("local_path"),
                        "cache_key": cache_key,
                    }
            try:
                response = await aclient.video.generate(
                    prompt=prompt,
                    model="grok-imagine-video",
                    video_url=video_url,
                    timeout=timedelta(minutes=20),
                    interval=timedelta(seconds=5),
                )
                result = {
                    "url": response.url,
                    "duration": getattr(response, "duration", None),
                    "error": None,
                    "cached": False,
                    "cache_key": cache_key,
                }
                if use_cache:
                    prompt_cache.store(cache_key, video_url=result["url"])
                return result
            except (VideoGenerationError, grpc.RpcError, TimeoutError) as e:
                err = _wrap_api_error(e)
                return {"url": None, "duration": None, "error": str(err)}

        return await asyncio.gather(*[one(p, u) for p, u in edits])

    def edit_variants(
        self,
        source_url: str,
        edit_prompts: list[str],
        *,
        on_progress: ProgressFn = _noop,
        use_cache: bool = True,
    ) -> list[dict]:
        on_progress(f"Edytuję {len(edit_prompts)} wariantów równolegle…")
        edits = [(p, source_url) for p in edit_prompts]
        return asyncio.run(self.edit_batch_async(edits, use_cache=use_cache))


def download_video(
    url: str,
    dest: Path,
    *,
    api_key: str | None = None,
    on_progress: ProgressFn = _noop,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    on_progress(f"Pobieram → {dest}")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with dest.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return dest


def iteration_video_path(session_id: str, iteration_id: str) -> Path:
    return Path(session_id) / f"{iteration_id}.mp4"

