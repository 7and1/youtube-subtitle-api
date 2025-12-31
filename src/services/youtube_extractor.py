from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|shorts\/)?([a-zA-Z0-9_-]{11})"
)


@dataclass(frozen=True)
class ExtractedSubtitles:
    video_id: str
    title: Optional[str]
    language: str
    subtitles: list[dict[str, Any]]
    plain_text: str
    extraction_method: str
    proxy_used: Optional[str]


def extract_video_id(video_id: Optional[str], video_url: Optional[str]) -> str:
    if video_id:
        if not VIDEO_ID_PATTERN.match(video_id):
            raise ValueError("Invalid video_id format")
        return video_id
    if video_url:
        match = YOUTUBE_URL_PATTERN.search(video_url)
        if match:
            return match.group(1)
    raise ValueError("Missing or invalid video_id/video_url")


def _clean_text_for_ai(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^(SPEAKER_\\d+:|>>>?\\s*)", "", text)
    text = re.sub(r"\\[.*?\\]", "", text)
    text = re.sub(r"\\(.*?\\)", "", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def clean_subtitles_for_ai(
    subtitles: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    cleaned: list[dict[str, Any]] = []
    all_text: list[str] = []
    for item in subtitles:
        text = _clean_text_for_ai(str(item.get("text", "")))
        if not text:
            continue
        cleaned.append(
            {"start": item.get("start"), "duration": item.get("duration"), "text": text}
        )
        all_text.append(text)

    plain = " ".join(all_text)
    plain = _remove_adjacent_duplicates(plain)
    return cleaned, plain


def _remove_adjacent_duplicates(text: str) -> str:
    words = text.split()
    if len(words) < 4:
        return text
    result: list[str] = []
    i = 0
    while i < len(words):
        found = False
        for length in (4, 3, 2):
            if i + length * 2 <= len(words):
                a = " ".join(words[i : i + length])
                b = " ".join(words[i + length : i + length * 2])
                if a.lower() == b.lower():
                    result.extend(words[i : i + length])
                    i += length * 2
                    found = True
                    break
        if not found:
            result.append(words[i])
            i += 1
    return " ".join(result)


async def fetch_oembed_title(video_id: str, timeout: float = 5.0) -> Optional[str]:
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            data = r.json()
            return data.get("title")
    except Exception:
        return None


def _parse_json3_subtitles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = payload.get("events") or []
    out: list[dict[str, Any]] = []
    for ev in events:
        if "segs" not in ev:
            continue
        start_ms = ev.get("tStartMs", 0)
        dur_ms = ev.get("dDurationMs", 0)
        segs = ev.get("segs") or []
        text = "".join((s.get("utf8") or "") for s in segs)
        text = text.replace("\\n", " ").strip()
        if not text:
            continue
        out.append(
            {"start": start_ms / 1000.0, "duration": dur_ms / 1000.0, "text": text}
        )
    return out


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
)
async def _download_json3(
    url: str, proxy_url: Optional[str], timeout: float
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout, proxy=proxy_url) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def _ytdlp_get_subtitle_url(
    video_id: str,
    language: str,
    proxy_url: Optional[str],
    timeout: int,
) -> tuple[Optional[str], Optional[str]]:
    import yt_dlp

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [language, "en"],
        "subtitlesformat": "json3",
        "socket_timeout": timeout,
    }
    if proxy_url:
        opts["proxy"] = proxy_url

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(
        None, lambda: yt_dlp.YoutubeDL(opts).extract_info(watch_url, download=False)
    )
    if not info:
        return None, None
    title = info.get("title")
    subtitles = info.get("subtitles") or info.get("automatic_captions") or {}
    candidates = subtitles.get(language) or subtitles.get("en") or []
    if not candidates:
        return title, None
    # Prefer json3
    json3 = next(
        (
            c
            for c in candidates
            if (c.get("ext") == "json3" or "json3" in str(c.get("ext", "")))
        ),
        None,
    )
    pick = json3 or candidates[0]
    return title, pick.get("url")


async def extract_with_youtube_transcript_api(
    video_id: str,
    language: str,
    proxies: Optional[dict[str, str]],
    timeout: int,
) -> list[dict[str, Any]]:
    loop = asyncio.get_event_loop()

    def _fetch() -> list[dict[str, Any]]:
        transcript_list = YouTubeTranscriptApi.list_transcripts(
            video_id, proxies=proxies
        )
        try:
            return transcript_list.find_manually_created_transcript([language]).fetch()
        except NoTranscriptFound:
            pass
        try:
            return transcript_list.find_generated_transcript([language]).fetch()
        except NoTranscriptFound:
            pass
        # Translation if possible
        for t in transcript_list:
            try:
                if t.is_translatable:
                    return t.translate(language).fetch()
            except Exception:
                continue
        for t in transcript_list:
            return t.fetch()
        raise NoTranscriptFound(video_id)

    raw = await asyncio.wait_for(loop.run_in_executor(None, _fetch), timeout=timeout)
    return [
        {"start": i["start"], "duration": i["duration"], "text": i["text"]} for i in raw
    ]


async def extract_with_ytdlp(
    video_id: str,
    language: str,
    proxy_url: Optional[str],
    timeout: int,
) -> tuple[Optional[str], list[dict[str, Any]]]:
    title, sub_url = await asyncio.wait_for(
        _ytdlp_get_subtitle_url(
            video_id, language, proxy_url=proxy_url, timeout=timeout
        ),
        timeout=timeout,
    )
    if not sub_url:
        return title, []
    payload = await _download_json3(
        sub_url, proxy_url=proxy_url, timeout=float(timeout)
    )
    return title, _parse_json3_subtitles(payload)


async def extract_subtitles_dual_engine(
    *,
    video_id: str,
    language: str,
    timeout: int,
    use_proxy: bool,
    proxy_url: Optional[str],
    proxy_dict: Optional[dict[str, str]],
    fallback_enabled: bool = True,
    clean_for_ai: bool = True,
) -> ExtractedSubtitles:
    proxy_used = None
    method = "youtube-transcript-api"

    # 1) transcript-api (direct)
    try:
        subs = await extract_with_youtube_transcript_api(
            video_id, language, proxies=None, timeout=timeout
        )
        cleaned, plain = (
            clean_subtitles_for_ai(subs)
            if clean_for_ai
            else (subs, " ".join(s["text"] for s in subs))
        )
        title = await fetch_oembed_title(video_id)
        return ExtractedSubtitles(
            video_id=video_id,
            title=title,
            language=language,
            subtitles=cleaned,
            plain_text=plain,
            extraction_method=method,
            proxy_used=None,
        )
    except (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound):
        # Not retriable by proxy in many cases; let fallback try.
        pass
    except Exception as e:
        logger.info(
            "transcript_api_failed", extra={"video_id": video_id, "error": str(e)}
        )

    # 2) transcript-api via proxy (only if requested)
    if use_proxy and proxy_dict:
        try:
            proxy_used = proxy_url
            subs = await extract_with_youtube_transcript_api(
                video_id, language, proxies=proxy_dict, timeout=timeout
            )
            cleaned, plain = (
                clean_subtitles_for_ai(subs)
                if clean_for_ai
                else (subs, " ".join(s["text"] for s in subs))
            )
            title = await fetch_oembed_title(video_id)
            return ExtractedSubtitles(
                video_id=video_id,
                title=title,
                language=language,
                subtitles=cleaned,
                plain_text=plain,
                extraction_method=method,
                proxy_used=proxy_used,
            )
        except Exception as e:
            logger.info(
                "transcript_api_proxy_failed",
                extra={"video_id": video_id, "error": str(e)},
            )

    # 3) yt-dlp fallback (direct)
    if not fallback_enabled:
        raise RuntimeError("Subtitle extraction failed and fallback disabled")

    method = "yt-dlp"
    try:
        title, subs = await extract_with_ytdlp(
            video_id, language, proxy_url=None, timeout=timeout
        )
        if not subs and not title:
            raise RuntimeError("yt-dlp failed to find subtitles")
        cleaned, plain = (
            clean_subtitles_for_ai(subs)
            if clean_for_ai
            else (subs, " ".join(s["text"] for s in subs))
        )
        return ExtractedSubtitles(
            video_id=video_id,
            title=title,
            language=language,
            subtitles=cleaned,
            plain_text=plain,
            extraction_method=method,
            proxy_used=None,
        )
    except Exception as e:
        logger.info("ytdlp_failed", extra={"video_id": video_id, "error": str(e)})

    # 4) yt-dlp via proxy
    if use_proxy and proxy_url:
        title, subs = await extract_with_ytdlp(
            video_id, language, proxy_url=proxy_url, timeout=timeout
        )
        if not subs:
            raise RuntimeError("yt-dlp proxy failed to find subtitles")
        cleaned, plain = (
            clean_subtitles_for_ai(subs)
            if clean_for_ai
            else (subs, " ".join(s["text"] for s in subs))
        )
        return ExtractedSubtitles(
            video_id=video_id,
            title=title,
            language=language,
            subtitles=cleaned,
            plain_text=plain,
            extraction_method=method,
            proxy_used=proxy_url,
        )

    raise RuntimeError("Subtitle extraction failed")
