"""
Quick Start Examples for YouTube Subtitle API SDK

This file demonstrates common usage patterns for the SDK.
Run individual examples by uncommenting the code you want to try.
"""

import asyncio
import os
from youtube_subtitle_api import (
    YouTubeSubtitleAPI,
    AsyncYouTubeSubtitleAPI,
    Config,
    Subtitle,
    QueuedResponse,
)
from youtube_subtitle_api.errors import (
    YouTubeSubtitleAPIError,
    NotFoundError,
    RateLimitError,
)


# Configuration - Replace with your actual API key and base URL
API_KEY = os.getenv("YOUTUBE_SUBTITLE_API_KEY", "your-api-key")
BASE_URL = os.getenv("YOUTUBE_SUBTITLE_API_URL", "https://api.expertbeacon.com")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-webhook-secret")


def example_1_basic_usage():
    """Example 1: Basic synchronous usage with context manager."""
    print("Example 1: Basic Usage")
    print("-" * 50)

    # Use context manager for automatic cleanup
    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        # Extract subtitles using video ID
        result = client.extract_subtitles(
            video_id="dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
            language="en"
        )

        # Handle both cached results and queued jobs
        if isinstance(result, Subtitle):
            print(f"Got {len(result.subtitles)} subtitle items")
            print(f"Title: {result.title}")
            print(f"Duration: {result.total_duration:.1f} seconds")
            print(f"Word count: {result.word_count}")
            print(f"\nFirst line: {result.subtitles[0].text}")
        elif isinstance(result, QueuedResponse):
            print(f"Job queued: {result.job_id}")
            # Wait for completion
            subtitle = client.wait_for_job(result.job_id, timeout=60)
            print(f"Got {len(subtitle.subtitles)} subtitle items after waiting")

    print()


def example_2_using_url():
    """Example 2: Extract using YouTube URL instead of video ID."""
    print("Example 2: Using YouTube URL")
    print("-" * 50)

    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        # Extract using full YouTube URL
        result = client.extract_subtitles(
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            language="en"
        )

        if isinstance(result, Subtitle):
            print(f"Extracted from URL: {result.video_id}")
            print(f"Plain text preview: {result.plain_text[:200]}...")

    print()


def example_3_batch_processing():
    """Example 3: Batch processing multiple videos."""
    print("Example 3: Batch Processing")
    print("-" * 50)

    video_ids = [
        "dQw4w9WgXcQ",  # Example video ID
        # Add more video IDs as needed
    ]

    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        # Batch extraction
        batch_result = client.extract_batch(video_ids, language="en")

        print(f"Total videos: {batch_result.video_count}")
        print(f"Queued for extraction: {batch_result.queued_count}")
        print(f"Found in cache: {batch_result.cached_count}")

        # Wait for all queued jobs
        all_subtitles = []
        for job_id in batch_result.job_ids:
            try:
                subtitle = client.wait_for_job(job_id, timeout=120)
                all_subtitles.append(subtitle)
                print(f"  Job {job_id[:8]}... completed")
            except Exception as e:
                print(f"  Job {job_id[:8]}... failed: {e}")

        print(f"Total subtitles extracted: {len(all_subtitles)}")

    print()


def example_4_error_handling():
    """Example 4: Proper error handling."""
    print("Example 4: Error Handling")
    print("-" * 50)

    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        try:
            # Try to get subtitles that might not exist
            subtitle = client.get_subtitles("nonexistent_video_id")
            print(subtitle.plain_text)
        except NotFoundError as e:
            print(f"Not found: {e.message}")
            print(f"Hint: {e.hint}")
        except RateLimitError as e:
            print(f"Rate limited: {e.message}")
            print(f"Wait before retrying")
        except YouTubeSubtitleAPIError as e:
            print(f"API error: {e.message}")

    print()


def example_5_export_formats():
    """Example 5: Export subtitles in different formats."""
    print("Example 5: Export Formats")
    print("-" * 50)

    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        result = client.extract_subtitles("dQw4w9WgXcQ")

        if isinstance(result, Subtitle):
            # Export as SRT
            srt_content = result.to_srt()
            print("SRT format (first 200 chars):")
            print(srt_content[:200] + "...")

            print("\n" + "=" * 50 + "\n")

            # Export as VTT
            vtt_content = result.to_vtt()
            print("VTT format (first 200 chars):")
            print(vtt_content[:200] + "...")

            # Save to files
            # with open("subtitles.srt", "w") as f:
            #     f.write(srt_content)
            # with open("subtitles.vtt", "w") as f:
            #     f.write(vtt_content)

    print()


def example_6_search_subtitles():
    """Example 6: Search within subtitles."""
    print("Example 6: Search Subtitles")
    print("-" * 50)

    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        result = client.extract_subtitles("dQw4w9WgXcQ")

        if isinstance(result, Subtitle):
            # Search for specific text
            query = "never"
            matches = result.search_text(query)

            print(f"Found {len(matches)} matches for '{query}':")
            for item in matches[:5]:  # Show first 5 matches
                print(f"  [{item.start:.1f}s] {item.text}")

            # Get subtitles by time range
            print(f"\nSubtitles from 10-20 seconds:")
            items = result.get_text_by_time_range(10.0, 20.0)
            for item in items:
                print(f"  [{item.start:.1f}s] {item.text}")

    print()


def example_7_custom_config():
    """Example 7: Using custom configuration."""
    print("Example 7: Custom Configuration")
    print("-" * 50)

    # Create a custom config
    config = Config(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=60.0,  # 60 second timeout
        webhook_secret=WEBHOOK_SECRET,
    )

    client = YouTubeSubtitleAPI(config=config)

    try:
        # Check API health
        health = client.health()
        print(f"API Status: {health.get('status', 'unknown')}")
    finally:
        client.close()

    print()


async def example_8_async_usage():
    """Example 8: Asynchronous usage."""
    print("Example 8: Async Usage")
    print("-" * 50)

    async with AsyncYouTubeSubtitleAPI(api_key=API_KEY) as client:
        result = await client.extract_subtitles("dQw4w9WgXcQ")

        if isinstance(result, Subtitle):
            print(f"Got {len(result.subtitles)} subtitle items (async)")
        elif isinstance(result, QueuedResponse):
            subtitle = await client.wait_for_job(result.job_id, timeout=60)
            print(f"Got {len(subtitle.subtitles)} subtitle items after waiting")

    print()


async def example_9_parallel_extraction():
    """Example 9: Parallel extraction with async client."""
    print("Example 9: Parallel Extraction")
    print("-" * 50)

    video_ids = [
        "dQw4w9WgXcQ",
        # Add more video IDs
    ]

    async with AsyncYouTubeSubtitleAPI(api_key=API_KEY) as client:
        # Extract multiple videos in parallel
        results = await client.extract_subtitles_batch_parallel(
            video_ids,
            concurrency=5,
            language="en"
        )

        for video_id, result in results:
            if isinstance(result, Exception):
                print(f"{video_id}: ERROR - {result}")
            elif isinstance(result, Subtitle):
                print(f"{video_id}: {len(result.subtitles)} items, {result.word_count} words")
            elif isinstance(result, QueuedResponse):
                print(f"{video_id}: Queued - {result.job_id}")

    print()


def example_10_get_job_status():
    """Example 10: Check job status without waiting."""
    print("Example 10: Job Status")
    print("-" * 50)

    with YouTubeSubtitleAPI(api_key=API_KEY) as client:
        # Start an extraction (will likely queue)
        result = client.extract_subtitles("some_video_id")

        if isinstance(result, QueuedResponse):
            job_id = result.job_id
            print(f"Job ID: {job_id}")

            # Check status without blocking
            job = client.get_job_status(job_id)
            print(f"Status: {job.status}")
            print(f"Is pending: {job.is_pending}")
            print(f"Is complete: {job.is_complete}")
            print(f"Is failed: {job.is_failed}")

    print()


def main():
    """Run all examples."""
    print("=" * 50)
    print("YouTube Subtitle API SDK - Quick Start Examples")
    print("=" * 50)
    print()

    # Run synchronous examples
    example_1_basic_usage()
    example_2_using_url()
    example_3_batch_processing()
    example_4_error_handling()
    example_5_export_formats()
    example_6_search_subtitles()
    example_7_custom_config()
    example_10_get_job_status()

    # Run async examples
    print("\nRunning async examples...")
    asyncio.run(example_8_async_usage())
    asyncio.run(example_9_parallel_extraction())

    print("\nAll examples completed!")


if __name__ == "__main__":
    # Uncomment to run all examples
    # main()

    # Or run individual examples
    example_1_basic_usage()
    # example_2_using_url()
    # example_3_batch_processing()
    # example_4_error_handling()
    # example_5_export_formats()
    # example_6_search_subtitles()
    # example_7_custom_config()
    # asyncio.run(example_8_async_usage())
    # asyncio.run(example_9_parallel_extraction())
    # example_10_get_job_status()
