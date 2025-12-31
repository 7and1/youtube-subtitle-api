# YouTube Subtitle API SDK - Python

A modern, type-hinted Python SDK for interacting with the YouTube Subtitle API. Extract subtitles from YouTube videos with support for both synchronous and asynchronous operations.

## Features

- **Modern Python 3.11+** with full type hints
- **Sync & Async** clients for any use case
- **Webhook Support** with signature verification
- **Intuitive API** with helpful error messages
- **Batch Operations** for processing multiple videos
- **SRT/VTT Export** for subtitle files
- **Context Manager** support for automatic cleanup

## Installation

```bash
pip install youtube-subtitle-api-sdk
```

With optional dev dependencies:

```bash
pip install youtube-subtitle-api-sdk[dev]
```

## Quick Start

### Synchronous Usage

```python
from youtube_subtitle_api import YouTubeSubtitleAPI

# Initialize the client
client = YouTubeSubtitleAPI(api_key="your-api-key")

# Extract subtitles (returns cached result or queues job)
result = client.extract_subtitles("dQw4w9WgXcQ", language="en")

# Handle both cached results and queued jobs
if isinstance(result, Subtitle):
    print(f"Got {len(result.subtitles)} subtitle items")
    print(result.plain_text)
else:  # QueuedResponse
    print(f"Job queued: {result.job_id}")
    # Wait for completion
    subtitle = client.wait_for_job(result.job_id, timeout=60)
    print(subtitle.plain_text)

# Clean up
client.close()
```

### Using Context Manager

```python
from youtube_subtitle_api import YouTubeSubtitleAPI

with YouTubeSubtitleAPI(api_key="your-api-key") as client:
    subtitle = client.extract_subtitles("dQw4w9WgXcQ")
    print(subtitle.plain_text)
```

### Asynchronous Usage

```python
import asyncio
from youtube_subtitle_api import AsyncYouTubeSubtitleAPI

async def main():
    async with AsyncYouTubeSubtitleAPI(api_key="your-api-key") as client:
        result = await client.extract_subtitles("dQw4w9WgXcQ")

        if isinstance(result, Subtitle):
            print(f"Got {len(result.subtitles)} subtitle items")
        else:
            subtitle = await client.wait_for_job(result.job_id)
            print(subtitle.plain_text)

asyncio.run(main())
```

## Configuration

```python
from youtube_subtitle_api import YouTubeSubtitleAPI, Config

# Using Config object
config = Config(
    api_key="your-api-key",
    base_url="https://api.expertbeacon.com",
    timeout=30.0,
    webhook_secret="your-webhook-secret",
)

client = YouTubeSubtitleAPI(config=config)
```

## API Reference

### YouTubeSubtitleAPI

The main synchronous client class.

#### Methods

##### `extract_subtitles(video_id, language="en", video_url=None, clean_for_ai=True, webhook_url=None)`

Extract subtitles for a YouTube video. Returns cached subtitles immediately if available, otherwise queues an extraction job.

**Parameters:**

- `video_id` (str): YouTube video ID (11 characters)
- `language` (str): Subtitle language code (default: "en")
- `video_url` (str): Full YouTube URL (alternative to video_id)
- `clean_for_ai` (bool): Normalize text for AI consumption (default: True)
- `webhook_url` (str): Optional webhook URL for completion notification

**Returns:** `Subtitle` if cached, `QueuedResponse` if queued

**Example:**

```python
# Using video ID
result = client.extract_subtitles("dQw4w9WgXcQ")

# Using URL
result = client.extract_subtitles(
    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="en"
)

# With webhook
result = client.extract_subtitles(
    "dQw4w9WgXcQ",
    webhook_url="https://your-app.com/webhook"
)
```

##### `get_subtitles(video_id, language="en")`

Get cached subtitles for a video. Only returns cached results.

**Parameters:**

- `video_id` (str): YouTube video ID
- `language` (str): Subtitle language code

**Returns:** `Subtitle` object

**Raises:** `NotFoundError` if not cached

**Example:**

```python
try:
    subtitle = client.get_subtitles("dQw4w9WgXcQ")
    print(subtitle.plain_text)
except NotFoundError:
    print("Not cached - use extract_subtitles()")
```

##### `extract_batch(video_ids, language="en", clean_for_ai=True, webhook_url=None)`

Extract subtitles for multiple videos in batch.

**Parameters:**

- `video_ids` (list[str]): List of YouTube video IDs (max 100)
- `language` (str): Subtitle language code
- `clean_for_ai` (bool): Normalize text for AI consumption
- `webhook_url` (str): Optional webhook URL

**Returns:** `BatchExtractionResult` object

**Example:**

```python
result = client.extract_batch(["id1", "id2", "id3"])
print(f"Queued: {result.queued_count}, Cached: {result.cached_count}")

for job_id in result.job_ids:
    subtitle = client.wait_for_job(job_id)
```

##### `get_job_status(job_id)`

Get the status of an extraction job.

**Parameters:**

- `job_id` (str): Job identifier

**Returns:** `JobInfo` object

**Example:**

```python
job = client.get_job_status(job_id)

if job.is_complete:
    print(job.subtitle.plain_text)
elif job.is_failed:
    print(f"Failed: {job.exc_info}")
else:
    print(f"Status: {job.status}")
```

##### `wait_for_job(job_id, timeout=60, poll_interval=2)`

Wait for a job to complete and return the subtitle.

**Parameters:**

- `job_id` (str): Job identifier
- `timeout` (float): Maximum time to wait in seconds
- `poll_interval` (float): Time between polls in seconds

**Returns:** `Subtitle` object

**Raises:** `TimeoutError` if job doesn't complete within timeout

**Example:**

```python
try:
    subtitle = client.wait_for_job(job_id, timeout=120)
    print(subtitle.plain_text)
except TimeoutError:
    print("Job took too long")
```

### AsyncYouTubeSubtitleAPI

The asynchronous client class with the same methods as `YouTubeSubtitleAPI` but using `async/await`.

**Additional Method:**

##### `extract_subtitles_batch_parallel(video_ids, language="en", clean_for_ai=True, concurrency=5)`

Extract subtitles for multiple videos in parallel.

**Parameters:**

- `video_ids` (list[str]): List of YouTube video IDs
- `language` (str): Subtitle language code
- `clean_for_ai` (bool): Normalize text for AI consumption
- `concurrency` (int): Maximum concurrent requests

**Returns:** List of `(video_id, result)` tuples

**Example:**

```python
results = await client.extract_subtitles_batch_parallel(
    ["id1", "id2", "id3"],
    concurrency=5
)

for video_id, result in results:
    if isinstance(result, Exception):
        print(f"{video_id} failed: {result}")
    elif isinstance(result, Subtitle):
        print(f"{video_id}: {len(result.subtitles)} items")
```

### Subtitle Model

The `Subtitle` dataclass represents extracted subtitle data.

**Attributes:**

- `video_id` (str): YouTube video ID
- `title` (str | None): Video title
- `language` (str): Subtitle language code
- `subtitles` (list[SubtitleItem]): List of subtitle items
- `plain_text` (str | None): Full transcript as plain text
- `subtitle_count` (int): Number of subtitle items
- `extraction_method` (str | None): Method used for extraction
- `cached` (bool): Whether result came from cache
- `created_at` (str | None): Creation timestamp

**Methods:**

##### `to_srt()`

Export subtitles in SRT format.

```python
subtitle = client.extract_subtitles("dQw4w9WgXcQ")
with open("subtitles.srt", "w") as f:
    f.write(subtitle.to_srt())
```

##### `to_vtt()`

Export subtitles in WebVTT format.

```python
vtt_content = subtitle.to_vtt()
```

##### `search_text(query, case_sensitive=False)`

Search for subtitle items containing text.

```python
matches = subtitle.search_text("hello")
for item in matches:
    print(f"{item.start}s: {item.text}")
```

##### `get_text_by_time_range(start, end=None)`

Get subtitles within a time range.

```python
items = subtitle.get_text_by_time_range(10.0, 20.0)
```

**Properties:**

- `total_duration`: Total duration in seconds
- `word_count`: Total word count of transcript

### SubtitleItem Model

Represents a single subtitle entry.

**Attributes:**

- `text` (str): Subtitle text
- `start` (float): Start time in seconds
- `end` (float): End time in seconds
- `dur` (float | None): Duration in seconds

## Error Handling

The SDK provides specific exception types for different errors:

```python
from youtube_subtitle_api import YouTubeSubtitleAPI
from youtube_subtitle_api.errors import (
    YouTubeSubtitleAPIError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    InvalidVideoIDError,
)

client = YouTubeSubtitleAPI(api_key="your-api-key")

try:
    result = client.extract_subtitles("invalid_id")
except AuthenticationError:
    print("Invalid API key")
except RateLimitError:
    print("Too many requests, wait before retrying")
except NotFoundError:
    print("Subtitles not found")
except InvalidVideoIDError:
    print("Invalid video ID format")
except YouTubeSubtitleAPIError as e:
    print(f"API error: {e.message}")
```

**Exception Hierarchy:**

- `YouTubeSubtitleAPIError` (base)
  - `APIError` (generic API error)
  - `AuthenticationError` (401)
  - `RateLimitError` (429)
  - `NotFoundError` (404)
  - `ValidationError` (400)
    - `InvalidVideoIDError`
  - `ServiceUnavailableError` (503)
  - `TimeoutError`
  - `NetworkError`

## Webhook Support

### Setting Up Webhook Handler

```python
from fastapi import FastAPI, Request, HTTPException
from youtube_subtitle_api.webhook import verify_signature, parse_webhook

app = FastAPI()
WEBHOOK_SECRET = "your-webhook-secret"

@app.post("/webhook/subtitle")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")

    # Verify signature
    if not verify_signature(payload, signature, WEBHOOK_SECRET, timestamp):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse webhook
    event = parse_webhook(payload)

    if event.is_success:
        subtitle = event.subtitle
        print(f"Job {event.job_id} completed: {len(subtitle.subtitles)} items")
    else:
        print(f"Job {event.job_id} failed: {event.error}")

    return {"status": "received"}
```

### Using WebhookVerifier

```python
from youtube_subtitle_api.webhook import WebhookVerifier

verifier = WebhookVerifier(secret="your-webhook-secret")

@app.post("/webhook/subtitle")
async def handle_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("X-Webhook-Signature", "")
    ts = request.headers.get("X-Webhook-Timestamp", "")

    try:
        event = verifier.verify_and_parse(payload, sig, ts)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid signature")

    return process_event(event)
```

## Advanced Examples

### Batch Processing with Progress

```python
from youtube_subtitle_api import YouTubeSubtitleAPI

video_ids = ["id1", "id2", "id3", "id4", "id5"]

with YouTubeSubtitleAPI(api_key="your-api-key") as client:
    # Start batch extraction
    result = client.extract_batch(video_ids)

    print(f"Queued: {result.queued_count}, Cached: {result.cached_count}")

    # Wait for all jobs
    subtitles = []
    for job_id in result.job_ids:
        subtitle = client.wait_for_job(job_id, timeout=120)
        subtitles.append(subtitle)
        print(f"Completed {len(subtitles)}/{len(result.job_ids)}")

    print(f"Total: {len(subtitles)} subtitles extracted")
```

### Parallel Extraction (Async)

```python
import asyncio
from youtube_subtitle_api import AsyncYouTubeSubtitleAPI

async def extract_multiple(video_ids):
    async with AsyncYouTubeSubtitleAPI(api_key="your-api-key") as client:
        results = await client.extract_subtitles_batch_parallel(
            video_ids,
            concurrency=10
        )

        for video_id, result in results:
            if isinstance(result, Exception):
                print(f"{video_id} failed: {result}")
            elif isinstance(result, Subtitle):
                print(f"{video_id}: {result.word_count} words")

asyncio.run(extract_multiple(["id1", "id2", "id3"]))
```

### Export to Different Formats

```python
from youtube_subtitle_api import YouTubeSubtitleAPI

with YouTubeSubtitleAPI(api_key="your-api-key") as client:
    subtitle = client.extract_subtitles("dQw4w9WgXcQ")

    # Export as SRT
    with open("output.srt", "w") as f:
        f.write(subtitle.to_srt())

    # Export as VTT
    with open("output.vtt", "w") as f:
        f.write(subtitle.to_vtt())

    # Export as plain text
    with open("output.txt", "w") as f:
        f.write(subtitle.plain_text)
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting

```bash
black youtube_subtitle_api/
ruff check youtube_subtitle_api/
```

### Type Checking

```bash
mypy youtube_subtitle_api/
```

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: https://docs.expertbeacon.com/youtube-subtitle-api
- Bug Reports: https://github.com/expertbeacon/youtube-subtitle-api/issues
- Email: support@expertbeacon.com
