# YouTube Subtitle API - User Guide

**Version:** 1.0.0 | **Last Updated:** 2025-12-31

This guide helps you get started with the YouTube Subtitle API in 5 minutes.

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Making Your First Request](#making-your-first-request)
- [Understanding Responses](#understanding-responses)
- [Common Use Cases](#common-use-cases)
- [Next Steps](#next-steps)

---

## Quick Start

### Prerequisites

- API base URL (e.g., `https://api.example.com`)
- API key (if authentication is enabled)

### Your First API Call (30 seconds)

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'
```

**Expected Response:**

If subtitles are cached:

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Never Gonna Give You Up",
  "language": "en",
  "subtitles": [
    { "text": "Never gonna give you up", "start": 1.5, "duration": 2.0 },
    { "text": "Never gonna let you down", "start": 3.5, "duration": 2.0 }
  ],
  "plain_text": "Never gonna give you up\nNever gonna let you down",
  "cached": true,
  "cache_tier": "redis"
}
```

If extraction is needed:

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "video_id": "dQw4w9WgXcQ",
  "language": "en"
}
```

---

## Authentication

### API Key Authentication

If the API has authentication enabled, include your API key in the request header:

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### JWT Authentication (Alternative)

Some deployments use JWT bearer tokens:

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_jwt_token_here" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### Getting Your API Key

Contact your API administrator to obtain an API key. Do not share your API key or commit it to version control.

---

## Making Your First Request

### Request Formats

You can provide YouTube videos in two ways:

#### 1. Using a Video URL

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }'
```

#### 2. Using a Video ID

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "dQw4w9WgXcQ"
  }'
```

### Request Parameters

| Parameter      | Type    | Required | Default | Description                                 |
| -------------- | ------- | -------- | ------- | ------------------------------------------- |
| `video_url`    | string  | No\*     | -       | Full YouTube URL                            |
| `video_id`     | string  | No\*     | -       | 11-character YouTube video ID               |
| `language`     | string  | No       | `en`    | Language code (e.g., `en`, `es`, `zh-Hans`) |
| `clean_for_ai` | boolean | No       | `true`  | Normalize text for AI processing            |
| `webhook_url`  | string  | No       | -       | URL for async completion notification       |

\*Either `video_url` or `video_id` is required.

### Supported URL Formats

- `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- `https://youtu.be/dQw4w9WgXcQ`
- `https://www.youtube.com/shorts/dQw4w9WgXcQ`

### Polling for Job Status

When a job is queued (HTTP 202), poll the job status endpoint:

```bash
curl "https://api.example.com/api/v1/job/abc123-def456-ghi789"
```

**Response when processing:**

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "enqueued_at": "2025-12-31T00:00:00Z"
}
```

**Response when complete:**

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "finished",
  "result": {
    "success": true,
    "video_id": "dQw4w9WgXcQ",
    "subtitles": [...],
    "plain_text": "Full transcript..."
  },
  "ended_at": "2025-12-31T00:00:05Z"
}
```

---

## Understanding Responses

### Successful Response (200)

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "language": "en",
  "extraction_method": "youtube-transcript-api",
  "subtitle_count": 150,
  "duration_ms": 1234,
  "subtitles": [
    {
      "text": "Subtitle text here",
      "start": 0.0,
      "duration": 2.5
    }
  ],
  "plain_text": "Full subtitle text without timestamps...",
  "proxy_used": false,
  "cached": true,
  "cache_tier": "redis",
  "created_at": "2025-12-31T00:00:00Z"
}
```

### Field Descriptions

| Field               | Type    | Description                                                |
| ------------------- | ------- | ---------------------------------------------------------- |
| `success`           | boolean | `true` if extraction succeeded                             |
| `video_id`          | string  | YouTube video ID                                           |
| `title`             | string  | Video title from YouTube                                   |
| `language`          | string  | Language code of subtitles                                 |
| `extraction_method` | string  | Method used: `youtube-transcript-api` or `yt-dlp`          |
| `subtitle_count`    | number  | Number of subtitle segments                                |
| `duration_ms`       | number  | Extraction time in milliseconds                            |
| `subtitles`         | array   | Array of subtitle objects with `text`, `start`, `duration` |
| `plain_text`        | string  | Full transcript without timestamps                         |
| `cached`            | boolean | Whether result was from cache                              |
| `cache_tier`        | string  | Cache level: `memory`, `redis`, or `postgres`              |
| `created_at`        | string  | ISO 8601 timestamp of extraction                           |

### Queued Response (202)

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "webhook_url": "https://your-app.com/webhook"
}
```

### Error Response (4xx/5xx)

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "hint": "Wait before making another request or upgrade your API plan",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z",
    "meta": {
      "retry_after": 45,
      "reset_at": "2025-12-31T00:01:00Z"
    }
  }
}
```

See [ERROR_CODES.md](ERROR_CODES.md) for all error codes.

---

## Common Use Cases

### 1. Get Subtitles for a Single Video

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'
```

### 2. Batch Process Multiple Videos

```bash
curl -X POST "https://api.example.com/api/v1/subtitles/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["dQw4w9WgXcQ", "anotherVideoId", "thirdVideoId"],
    "language": "en"
  }'
```

**Response:**

```json
{
  "status": "queued",
  "video_count": 3,
  "queued_count": 2,
  "cached_count": 1,
  "job_ids": ["job1", "job2"],
  "cached": ["dQw4w9WgXcQ"]
}
```

### 3. Get Cached Subtitles Only

```bash
curl "https://api.example.com/api/v1/subtitles/dQw4w9WgXcQ?language=en"
```

Returns 404 if not cached (does not trigger extraction).

### 4. Get Subtitles for Different Languages

```bash
# English
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -d '{"video_id": "dQw4w9WgXcQ", "language": "en"}'

# Spanish
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -d '{"video_id": "dQw4w9WgXcQ", "language": "es"}'

# Chinese Simplified
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -d '{"video_id": "dQw4w9WgXcQ", "language": "zh-Hans"}'
```

### 5. Get Raw Text Only (Cleaned for AI)

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -d '{"video_id": "dQw4w9WgXcQ", "clean_for_ai": true}'
```

Then access `plain_text` in the response.

### 6. Use Webhooks for Async Notification

Instead of polling, provide a webhook URL:

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "webhook_url": "https://your-app.com/webhook/subtitle"
  }'
```

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for webhook implementation details.

---

## Response Headers

All API responses include useful headers:

### Rate Limit Headers

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1735629600
X-RateLimit-Policy: 30;w=60;burst=5
```

### Request Tracing

```
X-Request-ID: abc123def456
X-API-Version: v1
```

Include the `X-Request-ID` when reporting issues for faster debugging.

---

## Rate Limiting

- **Default:** 30 requests per minute per IP
- **Burst:** 5 additional requests allowed
- **Response:** HTTP 429 when exceeded

See [RATE_LIMITING.md](RATE_LIMITING.md) for details on handling rate limits.

---

## Next Steps

- **Integration Examples:** See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for Python, JavaScript, and more
- **Error Handling:** See [ERROR_CODES.md](ERROR_CODES.md) for troubleshooting
- **Rate Limits:** See [RATE_LIMITING.md](RATE_LIMITING.md) for best practices
- **Full API Reference:** See [API-README.md](API-README.md) for complete endpoint documentation

---

## Support

For issues or questions:

- Include your `X-Request-ID` from response headers
- Check [ERROR_CODES.md](ERROR_CODES.md) for common issues
- Contact your API administrator
