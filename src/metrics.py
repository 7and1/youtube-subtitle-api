from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

extraction_requests_total = Counter(
    "youtube_subtitles_extraction_requests_total",
    "Total extraction requests received (including cache hits).",
    ["endpoint"],
)

cache_hits_total = Counter(
    "youtube_subtitles_cache_hits_total",
    "Total cache hits by tier.",
    ["tier"],
)

cache_misses_total = Counter(
    "youtube_subtitles_cache_misses_total",
    "Total cache misses (no cached result found).",
)

extraction_success_total = Counter(
    "youtube_subtitles_extraction_success_total",
    "Total successful extractions.",
    ["method"],
)

extraction_failure_total = Counter(
    "youtube_subtitles_extraction_failure_total",
    "Total failed extractions.",
    ["method"],
)

extraction_duration_seconds = Histogram(
    "youtube_subtitles_extraction_duration_seconds",
    "Duration of subtitle extraction jobs.",
    ["method"],
    buckets=(0.25, 0.5, 1, 2, 5, 10, 20, 30, 60),
)

job_queue_depth = Gauge(
    "youtube_subtitles_job_queue_depth",
    "Current Redis job queue depth (RQ queue length).",
)
