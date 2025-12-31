"""
Subtitle extraction service with dual-engine approach.
Primary: youtube-transcript-api (fast, no dependencies)
Fallback: yt-dlp (robust, handles edge cases)

Features:
- Proxy rotation support
- Automatic failover between engines
- VTT cleaning for AI consumption
"""
import os
import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import structlog
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)

from app.services.proxy_manager import get_proxy_manager, Proxy

logger = structlog.get_logger(__name__)

EXTRACTION_TIMEOUT = int(os.getenv("EXTRACTION_TIMEOUT", "30"))
FALLBACK_ENABLED = os.getenv("FALLBACK_ENABLED", "true").lower() == "true"
USE_PROXY = os.getenv("USE_PROXY", "true").lower() == "true"
PROXY_RETRY_COUNT = int(os.getenv("PROXY_RETRY_COUNT", "3"))


@dataclass
class SubtitleResult:
    """Result of subtitle extraction."""
    success: bool
    video_id: str
    title: Optional[str] = None
    extraction_method: str = ""
    subtitles: list = field(default_factory=list)
    plain_text: Optional[str] = None
    error: Optional[str] = None
    proxy_used: Optional[str] = None


class SubtitleService:
    """
    Dual-engine subtitle extraction service with proxy support.

    Strategy:
    1. Try youtube-transcript-api first (fast, lightweight)
    2. If it fails and fallback is enabled, try yt-dlp
    3. Use proxy rotation when USE_PROXY=true
    4. Clean VTT formatting for AI consumption if requested
    """

    def __init__(self):
        self.timeout = EXTRACTION_TIMEOUT
        self.fallback_enabled = FALLBACK_ENABLED
        self.use_proxy = USE_PROXY
        self.proxy_manager = get_proxy_manager() if USE_PROXY else None

    async def extract(
        self,
        video_id: str,
        language: str = "en",
        clean_for_ai: bool = True
    ) -> SubtitleResult:
        """
        Extract subtitles from a YouTube video.

        Strategy (Direct First, Proxy on Failure):
        1. Try youtube-transcript-api with direct connection (no proxy)
        2. If network/rate-limit error and proxies available, retry with proxy
        3. If still fails and fallback enabled, try yt-dlp direct
        4. If yt-dlp fails with network error and proxies available, retry with proxy

        Args:
            video_id: YouTube video ID (11 characters)
            language: Preferred subtitle language code
            clean_for_ai: Whether to clean VTT formatting

        Returns:
            SubtitleResult with subtitles or error
        """
        # Step 1: Try primary method with DIRECT connection (no proxy)
        result = await self._extract_with_transcript_api(video_id, language, use_proxy=False)

        if result.success:
            if clean_for_ai:
                result = self._clean_for_ai(result)
            return result

        # Step 2: If network/rate-limit error, retry with proxy
        if self._is_proxy_retriable_error(result.error) and self._has_available_proxy():
            logger.info("retrying_with_proxy", video_id=video_id, direct_error=result.error)
            result = await self._extract_with_transcript_api(video_id, language, use_proxy=True)

            if result.success:
                if clean_for_ai:
                    result = self._clean_for_ai(result)
                return result

        # Step 3: Try fallback method (yt-dlp) with DIRECT connection
        if self.fallback_enabled:
            logger.info("trying_fallback", video_id=video_id, primary_error=result.error)
            result = await self._extract_with_ytdlp(video_id, language, use_proxy=False)

            if result.success:
                if clean_for_ai:
                    result = self._clean_for_ai(result)
                return result

            # Step 4: If yt-dlp also fails with network error, retry with proxy
            if self._is_proxy_retriable_error(result.error) and self._has_available_proxy():
                logger.info("ytdlp_retrying_with_proxy", video_id=video_id, direct_error=result.error)
                result = await self._extract_with_ytdlp(video_id, language, use_proxy=True)

                if result.success and clean_for_ai:
                    result = self._clean_for_ai(result)

            return result

        return result

    def _is_proxy_retriable_error(self, error: Optional[str]) -> bool:
        """Check if error is retriable with proxy (network/rate-limit issues)."""
        if not error:
            return False
        error_lower = error.lower()
        retriable_patterns = ['403', '429', 'blocked', 'rate limit', 'connection',
                              'timeout', 'proxy', 'forbidden', 'too many requests']
        return any(pattern in error_lower for pattern in retriable_patterns)

    def _has_available_proxy(self) -> bool:
        """Check if proxy rotation is enabled and proxies are available."""
        return self.use_proxy and self.proxy_manager and self.proxy_manager.has_proxies

    def _get_proxy(self) -> Optional[Proxy]:
        """Get a proxy if proxy mode is enabled."""
        if self.use_proxy and self.proxy_manager and self.proxy_manager.has_proxies:
            return self.proxy_manager.get_proxy()
        return None

    async def _extract_with_transcript_api(
        self,
        video_id: str,
        language: str,
        use_proxy: bool = False
    ) -> SubtitleResult:
        """Extract using youtube-transcript-api with optional proxy."""
        proxy = self._get_proxy() if use_proxy else None
        proxy_dict = proxy.url_dict if proxy else None
        proxy_info = f"{proxy.host}:{proxy.port}" if proxy else None

        try:
            loop = asyncio.get_event_loop()
            transcript = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._fetch_transcript(video_id, language, proxy_dict)
                ),
                timeout=self.timeout
            )

            if transcript is None:
                if proxy:
                    self.proxy_manager.mark_failure(proxy, "No transcript")
                return SubtitleResult(
                    success=False,
                    video_id=video_id,
                    extraction_method="youtube-transcript-api",
                    error="No transcript available",
                    proxy_used=proxy_info
                )

            # Mark proxy success
            if proxy:
                self.proxy_manager.mark_success(proxy)

            subtitles = [
                {
                    "start": item["start"],
                    "duration": item["duration"],
                    "text": item["text"]
                }
                for item in transcript
            ]

            return SubtitleResult(
                success=True,
                video_id=video_id,
                extraction_method="youtube-transcript-api",
                subtitles=subtitles,
                proxy_used=proxy_info
            )

        except asyncio.TimeoutError:
            if proxy:
                self.proxy_manager.mark_failure(proxy, "Timeout")
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="youtube-transcript-api",
                error=f"Extraction timed out after {self.timeout}s",
                proxy_used=proxy_info
            )
        except TranscriptsDisabled:
            # Not a proxy issue
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="youtube-transcript-api",
                error="Transcripts are disabled for this video",
                proxy_used=proxy_info
            )
        except NoTranscriptFound:
            # Not a proxy issue
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="youtube-transcript-api",
                error=f"No transcript found for language: {language}",
                proxy_used=proxy_info
            )
        except VideoUnavailable:
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="youtube-transcript-api",
                error="Video is unavailable",
                proxy_used=proxy_info
            )
        except Exception as e:
            error_str = str(e)
            # Check if it's a proxy/network error
            if proxy and any(x in error_str.lower() for x in ['proxy', 'connection', '403', '429', 'blocked']):
                self.proxy_manager.mark_failure(proxy, error_str)
            logger.error("transcript_api_error", video_id=video_id, error=error_str)
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="youtube-transcript-api",
                error=error_str,
                proxy_used=proxy_info
            )

    def _fetch_transcript(self, video_id: str, language: str, proxies: Optional[dict] = None) -> Optional[list]:
        """Synchronous transcript fetch with optional proxy."""
        try:
            # youtube-transcript-api supports proxies parameter
            transcript_list = YouTubeTranscriptApi.list_transcripts(
                video_id,
                proxies=proxies
            )

            # First try manual transcripts (higher quality)
            try:
                transcript = transcript_list.find_manually_created_transcript([language])
                return transcript.fetch()
            except NoTranscriptFound:
                pass

            # Then try auto-generated
            try:
                transcript = transcript_list.find_generated_transcript([language])
                return transcript.fetch()
            except NoTranscriptFound:
                pass

            # Try translation if available
            try:
                for t in transcript_list:
                    if t.is_translatable:
                        translated = t.translate(language)
                        return translated.fetch()
            except Exception:
                pass

            # Last resort: any available transcript
            for t in transcript_list:
                return t.fetch()

            return None

        except Exception:
            raise

    async def _extract_with_ytdlp(
        self,
        video_id: str,
        language: str,
        use_proxy: bool = False
    ) -> SubtitleResult:
        """Extract using yt-dlp as fallback with optional proxy."""
        proxy = self._get_proxy() if use_proxy else None
        proxy_url = proxy.url if proxy else None
        proxy_info = f"{proxy.host}:{proxy.port}" if proxy else None

        try:
            import yt_dlp

            url = f"https://www.youtube.com/watch?v={video_id}"

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [language, "en"],
                "subtitlesformat": "json3",
                "socket_timeout": self.timeout,
            }

            # Add proxy if available
            if proxy_url:
                ydl_opts["proxy"] = proxy_url

            loop = asyncio.get_event_loop()
            info = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._ytdlp_extract(url, ydl_opts)
                ),
                timeout=self.timeout
            )

            if info is None:
                if proxy:
                    self.proxy_manager.mark_failure(proxy, "No info")
                return SubtitleResult(
                    success=False,
                    video_id=video_id,
                    extraction_method="yt-dlp",
                    error="Failed to extract video info",
                    proxy_used=proxy_info
                )

            # Mark proxy success
            if proxy:
                self.proxy_manager.mark_success(proxy)

            title = info.get("title")
            subtitles_data = info.get("subtitles", {}) or info.get("automatic_captions", {})

            # Find subtitles in requested language
            subs = subtitles_data.get(language) or subtitles_data.get("en") or []

            if not subs:
                return SubtitleResult(
                    success=False,
                    video_id=video_id,
                    title=title,
                    extraction_method="yt-dlp",
                    error=f"No subtitles found for language: {language}",
                    proxy_used=proxy_info
                )

            # Parse subtitle data (varies by format)
            parsed_subs = self._parse_ytdlp_subtitles(subs)

            return SubtitleResult(
                success=True,
                video_id=video_id,
                title=title,
                extraction_method="yt-dlp",
                subtitles=parsed_subs,
                proxy_used=proxy_info
            )

        except asyncio.TimeoutError:
            if proxy:
                self.proxy_manager.mark_failure(proxy, "Timeout")
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="yt-dlp",
                error=f"yt-dlp timed out after {self.timeout}s",
                proxy_used=proxy_info
            )
        except Exception as e:
            error_str = str(e)
            if proxy and any(x in error_str.lower() for x in ['proxy', 'connection', '403', '429']):
                self.proxy_manager.mark_failure(proxy, error_str)
            logger.error("ytdlp_error", video_id=video_id, error=error_str)
            return SubtitleResult(
                success=False,
                video_id=video_id,
                extraction_method="yt-dlp",
                error=error_str,
                proxy_used=proxy_info
            )

    def _ytdlp_extract(self, url: str, opts: dict) -> Optional[dict]:
        """Synchronous yt-dlp extraction (runs in thread pool)."""
        import yt_dlp

        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _parse_ytdlp_subtitles(self, subs: list) -> list:
        """Parse yt-dlp subtitle format into standard format."""
        parsed = []

        for sub in subs:
            if isinstance(sub, dict):
                # JSON3 format has different structure
                if "url" in sub:
                    # Need to fetch the actual subtitle content
                    continue
                if "start" in sub or "tStartMs" in sub:
                    parsed.append({
                        "start": sub.get("start", sub.get("tStartMs", 0) / 1000),
                        "duration": sub.get("duration", sub.get("dDurationMs", 0) / 1000),
                        "text": sub.get("text", sub.get("segs", [{}])[0].get("utf8", ""))
                    })

        return parsed

    def _clean_for_ai(self, result: SubtitleResult) -> SubtitleResult:
        """
        Clean subtitles for AI consumption.

        Removes:
        - VTT formatting tags (<c>, <b>, etc.)
        - Timing cues embedded in text
        - Speaker labels
        - Redundant whitespace
        - Music/sound notations [Music]
        """
        cleaned_subs = []
        all_text = []

        for sub in result.subtitles:
            text = sub.get("text", "")

            # Remove VTT tags
            text = re.sub(r"<[^>]+>", "", text)

            # Remove speaker labels like "SPEAKER_01:" or ">>>"
            text = re.sub(r"^(SPEAKER_\d+:|>>>?\s*)", "", text)

            # Remove music/sound annotations
            text = re.sub(r"\[.*?\]", "", text)
            text = re.sub(r"\(.*?\)", "", text)

            # Clean whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Skip empty lines
            if not text:
                continue

            cleaned_subs.append({
                "start": sub.get("start"),
                "duration": sub.get("duration"),
                "text": text
            })
            all_text.append(text)

        # Generate plain text version
        plain_text = " ".join(all_text)

        # Clean up repeated phrases (common in auto-generated subs)
        plain_text = self._remove_duplicates(plain_text)

        result.subtitles = cleaned_subs
        result.plain_text = plain_text

        return result

    def _remove_duplicates(self, text: str) -> str:
        """Remove repeated phrases that occur in adjacent positions."""
        words = text.split()
        if len(words) < 4:
            return text

        result = []
        i = 0
        while i < len(words):
            # Check for 2-4 word phrase repetition
            found_dup = False
            for phrase_len in [4, 3, 2]:
                if i + phrase_len * 2 <= len(words):
                    phrase1 = " ".join(words[i:i + phrase_len])
                    phrase2 = " ".join(words[i + phrase_len:i + phrase_len * 2])
                    if phrase1.lower() == phrase2.lower():
                        result.extend(words[i:i + phrase_len])
                        i += phrase_len * 2
                        found_dup = True
                        break

            if not found_dup:
                result.append(words[i])
                i += 1

        return " ".join(result)

    def get_proxy_stats(self) -> Optional[dict]:
        """Get proxy pool statistics."""
        if self.proxy_manager:
            return self.proxy_manager.get_stats()
        return None
