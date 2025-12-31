# YouTube Subtitle API - Error Codes Reference

**Version:** 1.0.0 | **Last Updated:** 2025-12-31

This document lists all error codes returned by the YouTube Subtitle API, along with explanations and troubleshooting steps.

## Table of Contents

- [Error Response Format](#error-response-format)
- [Error Codes](#error-codes)
- [HTTP Status Codes](#http-status-codes)
- [Common Error Scenarios](#common-error-scenarios)
- [Troubleshooting Guide](#troubleshooting-guide)

---

## Error Response Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "hint": "Suggested action to fix the error",
    "request_id": "abc123def456",
    "timestamp": "2025-12-31T00:00:00Z",
    "meta": {
      "additional": "context-specific data"
    }
  }
}
```

### Response Headers

```
Content-Type: application/problem+json
X-Error-Code: ERROR_CODE
X-Request-ID: abc123def456
```

---

## Error Codes

### RATE_LIMIT_EXCEEDED

**HTTP Status:** 429

**Message:** Rate limit exceeded

**Hint:** Wait before making another request or upgrade your API plan

**Description:** You have exceeded the rate limit for your IP address or API key.

**Meta Fields:**

- `retry_after` (number): Seconds to wait before retrying
- `reset_at` (string): ISO 8601 timestamp when limit resets

**Example Response:**

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

**Troubleshooting:**

1. Wait for the number of seconds specified in `retry_after`
2. Check the `X-RateLimit-Remaining` header to track your remaining requests
3. Implement exponential backoff in your client
4. Consider caching results to reduce API calls
5. Contact support for higher rate limits if needed

See [RATE_LIMITING.md](RATE_LIMITING.md) for detailed rate limit handling.

---

### INVALID_VIDEO_ID

**HTTP Status:** 400

**Message:** Invalid YouTube video ID or URL format

**Hint:** Provide a valid 11-character video ID or full YouTube URL

**Description:** The provided video ID or URL is not in a valid format.

**Meta Fields:**

- `video_id` (string): The invalid video ID that was provided

**Example Response:**

```json
{
  "error": {
    "code": "INVALID_VIDEO_ID",
    "message": "Invalid video ID or URL format. Provide a valid 11-character YouTube video ID.",
    "hint": "Provide a valid 11-character video ID or full YouTube URL",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**Troubleshooting:**

1. Verify the video ID is exactly 11 characters
2. Valid video IDs contain: letters (a-z, A-Z), numbers (0-9), hyphens (-), and underscores (\_)
3. Extract video ID from YouTube URL:
   - `https://www.youtube.com/watch?v=dQw4w9WgXcQ` -> `dQw4w9WgXcQ`
   - `https://youtu.be/dQw4w9WgXcQ` -> `dQw4w9WgXcQ`
   - `https://www.youtube.com/shorts/dQw4w9WgXcQ` -> `dQw4w9WgXcQ`

**Valid Examples:**

```
dQw4w9WgXcQ
3tmd-ClpJxA
9bZkp7q19f0
```

**Invalid Examples:**

```
abc                    # Too short
dQw4w9WgXcQ123         # Too long
invalid@chars!         # Invalid characters
```

---

### SUBTITLE_NOT_FOUND

**HTTP Status:** 404

**Message:** Subtitles not found or not yet extracted

**Hint:** The video may not have subtitles in the requested language, or extraction is still pending

**Description:** Subtitles for the requested video and language combination are not available.

**Meta Fields:**

- `video_id` (string): The video ID
- `language` (string): The requested language code

**Example Response:**

```json
{
  "error": {
    "code": "SUBTITLE_NOT_FOUND",
    "message": "Subtitles not found for video dQw4w9WgXcQ in language en",
    "hint": "The video may not have subtitles in the requested language, or extraction is still pending",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z",
    "meta": {
      "video_id": "dQw4w9WgXcQ",
      "language": "en"
    }
  }
}
```

**Troubleshooting:**

1. **Check if extraction is pending:**

   ```bash
   curl "https://api.example.com/api/v1/job/{job_id}"
   ```

2. **Try triggering extraction:**

   ```bash
   curl -X POST "https://api.example.com/api/v1/subtitles" \
     -d '{"video_id": "dQw4w9WgXcQ", "language": "en"}'
   ```

3. **Try a different language:**
   - Some videos only have subtitles in specific languages
   - Try common codes: `en`, `es`, `fr`, `de`, `ja`, `ko`, `zh-Hans`, `zh-Hant`

4. **Verify the video has subtitles:**
   - Open the video on YouTube
   - Check if CC (closed captions) are available

5. **Video may not have any subtitles at all**
   - Some creators don't add subtitles
   - Auto-generated captions may not be available

---

### UNAUTHORIZED

**HTTP Status:** 401

**Message:** Authentication required

**Hint:** Provide a valid API key via X-API-Key header

**Description:** The request requires authentication but no valid credentials were provided.

**Example Response:**

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required",
    "hint": "Provide a valid API key via X-API-Key header",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**Troubleshooting:**

1. **Add API key header:**

   ```bash
   curl -X POST "https://api.example.com/api/v1/subtitles" \
     -H "X-API-Key: your_api_key_here" \
     -d '{"video_id": "dQw4w9WgXcQ"}'
   ```

2. **Verify API key is correct:**
   - Check for extra spaces or characters
   - Ensure you're using the correct key for the environment

3. **Contact administrator** if you don't have an API key

4. **For JWT authentication:**
   ```bash
   curl -X POST "https://api.example.com/api/v1/subtitles" \
     -H "Authorization: Bearer your_jwt_token" \
     -d '{"video_id": "dQw4w9WgXcQ"}'
   ```

---

### FORBIDDEN

**HTTP Status:** 403

**Message:** Access forbidden

**Hint:** You do not have permission to access this resource

**Description:** You don't have permission to access the requested resource.

**Example Response:**

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Access forbidden",
    "hint": "You do not have permission to access this resource",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**Troubleshooting:**

1. **Verify your API key has the required permissions**
2. **Contact administrator** to request access
3. **Check if you're accessing the correct endpoint** (admin endpoints require special access)

---

### INTERNAL_ERROR

**HTTP Status:** 500

**Message:** Internal server error

**Hint:** An unexpected error occurred. Please try again later

**Description:** The server encountered an unexpected error while processing your request.

**Example Response:**

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Internal server error",
    "hint": "An unexpected error occurred. Please try again later",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**Troubleshooting:**

1. **Retry the request** after a few seconds
2. **Check service status:**

   ```bash
   curl "https://api.example.com/health"
   ```

3. **Report the issue** with the `request_id` from the error response
4. **Temporary issues may include:**
   - Database connectivity problems
   - Redis connection issues
   - YouTube API temporary failures
   - Worker queue processing issues

---

### SERVICE_UNAVAILABLE

**HTTP Status:** 503

**Message:** Service temporarily unavailable

**Hint:** The service is experiencing issues. Please try again later

**Description:** The service is temporarily unable to handle the request.

**Example Response:**

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Service temporarily unavailable",
    "hint": "The service is experiencing issues. Please try again later",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**Troubleshooting:**

1. **Check health endpoint:**

   ```bash
   curl "https://api.example.com/health"
   ```

2. **Expected healthy response:**

   ```json
   {
     "status": "healthy",
     "components": {
       "api": "ready",
       "redis": "connected",
       "postgres": "connected"
     }
   }
   ```

3. **Wait and retry** - service may be under heavy load
4. **Check status page** if available
5. **Contact support** if issue persists

---

### INVALID_REQUEST

**HTTP Status:** 400

**Message:** Invalid request format

**Hint:** Check your request parameters and try again

**Description:** The request body or parameters are malformed or missing required fields.

**Example Response:**

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid request format",
    "hint": "Check your request parameters and try again",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**Troubleshooting:**

1. **Verify Content-Type header is set:**

   ```bash
   -H "Content-Type: application/json"
   ```

2. **Check request body is valid JSON:**

   ```bash
   echo '{"video_id": "dQw4w9WgXcQ"}' | jq .
   ```

3. **Ensure required fields are present:**
   - Either `video_url` or `video_id` is required
   - Batch requests require `video_ids` array

4. **Check field types:**
   - `video_ids` must be an array
   - `clean_for_ai` must be boolean
   - `language` must be a string

---

## HTTP Status Codes

| Status | Meaning               | Common Error Codes                    |
| ------ | --------------------- | ------------------------------------- |
| 200    | Success               | -                                     |
| 202    | Accepted (job queued) | -                                     |
| 400    | Bad Request           | `INVALID_REQUEST`, `INVALID_VIDEO_ID` |
| 401    | Unauthorized          | `UNAUTHORIZED`                        |
| 403    | Forbidden             | `FORBIDDEN`                           |
| 404    | Not Found             | `SUBTITLE_NOT_FOUND`                  |
| 429    | Too Many Requests     | `RATE_LIMIT_EXCEEDED`                 |
| 500    | Internal Server Error | `INTERNAL_ERROR`                      |
| 503    | Service Unavailable   | `SERVICE_UNAVAILABLE`                 |

---

## Common Error Scenarios

### Scenario 1: Video URL Not Recognized

**Error:** `INVALID_VIDEO_ID`

**Cause:** Malformed URL or video ID

**Solution:**

```python
import re

def extract_video_id(url):
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'  # Direct video ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL or video ID")

# Usage
video_id = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

---

### Scenario 2: Rate Limited During Batch Processing

**Error:** `RATE_LIMIT_EXCEEDED`

**Solution:**

```python
import time
import requests

def batch_with_backoff(api, video_ids, language="en"):
    """Process batch with rate limit handling."""
    results = []
    for i, video_id in enumerate(video_ids):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = api.extract_subtitles(video_id=video_id, language=language)
                results.append(result)

                # Check rate limit headers
                remaining = int(result.headers.get("X-RateLimit-Remaining", 0))
                if remaining < 5:
                    time.sleep(2)
                break

            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = e.response.json().get("error", {}).get("meta", {}).get("retry_after", 60)
                    print(f"Rate limited. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    if attempt == max_retries - 1:
                        raise
                else:
                    raise
    return results
```

---

### Scenario 3: Subtitle Extraction Failed

**Error:** Job status returns `failed`

**Solution:**

```python
def check_job_with_retry(api, job_id, max_wait=60):
    """Check job status with detailed error handling."""
    import time

    start = time.time()
    while time.time() - start < max_wait:
        status = api.get_job_status(job_id)

        if status["status"] == "finished":
            return status.get("result")
        elif status["status"] == "failed":
            error_info = status.get("exc_info", "Unknown error")
            print(f"Job failed: {error_info}")

            # Common failure patterns
            if "No subtitles found" in error_info:
                print("Video has no subtitles in the requested language")
            elif "Video unavailable" in error_info:
                print("Video is private, deleted, or region-restricted")
            elif "HTTP 429" in error_info:
                print("YouTube rate limited - try again later")

            raise Exception(f"Extraction failed: {error_info}")

        time.sleep(1)

    raise TimeoutError("Job did not complete in time")
```

---

## Troubleshooting Guide

### Debug Mode

Enable verbose logging to troubleshoot issues:

```bash
# Verbose cURL
curl -v "https://api.example.com/api/v1/subtitles/dQw4w9WgXcQ" \
  -H "X-API-Key: your_key"

# Check response headers
curl -I "https://api.example.com/health"
```

### Health Check

Always verify service health first:

```bash
curl "https://api.example.com/health"
```

**Expected output:**

```json
{
  "status": "healthy",
  "timestamp": "2025-12-31T00:00:00Z",
  "api_version": "v1",
  "components": {
    "api": "ready",
    "redis": "connected",
    "postgres": "connected"
  }
}
```

### Request ID Tracking

Include the `X-Request-ID` from error responses when reporting issues:

```python
def extract_with_tracking(api, video_id):
    try:
        return api.extract_subtitles(video_id=video_id)
    except Exception as e:
        request_id = getattr(e, "request_id", "unknown")
        print(f"Error occurred. Request ID: {request_id}")
        print(f"Report this ID to support for assistance")
        raise
```

---

## Next Steps

- [USER_GUIDE.md](USER_GUIDE.md) - Getting started guide
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Integration examples
- [RATE_LIMITING.md](RATE_LIMITING.md) - Rate limiting details
- [API-README.md](API-README.md) - Complete API reference
