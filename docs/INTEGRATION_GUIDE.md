# YouTube Subtitle API - Integration Guide

**Version:** 1.0.0 | **Last Updated:** 2025-12-31

This guide provides code examples and best practices for integrating the YouTube Subtitle API into your applications.

## Table of Contents

- [Python Integration](#python-integration)
- [JavaScript/Node.js Integration](#javascriptnodejs-integration)
- [cURL Examples](#curl-examples)
- [Error Handling Best Practices](#error-handling-best-practices)
- [Webhook Integration](#webhook-integration)
- [Rate Limit Handling](#rate-limit-handling)

---

## Python Integration

### Basic Setup

```python
import requests
import time
from typing import Optional, Dict, Any

class YouTubeSubtitleAPI:
    """Client for YouTube Subtitle API."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def extract_subtitles(
        self,
        video_url: Optional[str] = None,
        video_id: Optional[str] = None,
        language: str = "en",
        clean_for_ai: bool = True,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract subtitles for a YouTube video."""
        payload = {
            "language": language,
            "clean_for_ai": clean_for_ai
        }
        if video_url:
            payload["video_url"] = video_url
        elif video_id:
            payload["video_id"] = video_id
        else:
            raise ValueError("Either video_url or video_id is required")

        if webhook_url:
            payload["webhook_url"] = webhook_url

        response = self.session.post(
            f"{self.base_url}/api/v1/subtitles",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of an extraction job."""
        response = self.session.get(
            f"{self.base_url}/api/v1/job/{job_id}",
            headers=self._headers(),
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def wait_for_job(
        self,
        job_id: str,
        max_wait: int = 60,
        poll_interval: float = 1.0
    ) -> Dict[str, Any]:
        """Wait for a job to complete and return the result."""
        start = time.time()
        while time.time() - start < max_wait:
            status = self.get_job_status(job_id)
            if status["status"] in ("finished", "failed", "not_found"):
                return status
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not complete within {max_wait} seconds")

    def extract_and_wait(
        self,
        video_url: Optional[str] = None,
        video_id: Optional[str] = None,
        language: str = "en",
        max_wait: int = 60
    ) -> Dict[str, Any]:
        """Extract subtitles and wait for completion (handles both sync and async)."""
        result = self.extract_subtitles(video_url, video_id, language)

        # If immediately returned, we have the result
        if "subtitles" in result:
            return result

        # Otherwise, wait for the job to complete
        if "job_id" in result:
            job_result = self.wait_for_job(result["job_id"], max_wait=max_wait)
            if job_result["status"] == "finished" and job_result.get("result"):
                return job_result["result"]
            elif job_result["status"] == "failed":
                raise Exception(f"Job failed: {job_result.get('exc_info')}")

        raise Exception("Unexpected response format")
```

### Usage Examples

#### Basic Usage

```python
# Initialize client
api = YouTubeSubtitleAPI(
    base_url="https://api.example.com",
    api_key="your_api_key_here"  # Omit if no auth
)

# Get subtitles
result = api.extract_and_wait(
    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="en"
)

print(f"Title: {result['title']}")
print(f"Subtitles: {result['subtitle_count']}")
print(f"Plain text: {result['plain_text'][:200]}...")
```

#### With AsyncIO and Webhooks

```python
import asyncio
from aiohttp import web
import hmac
import hashlib
import json

class WebhookHandler:
    """Handle webhook notifications from the API."""

    def __init__(self, webhook_secret: str):
        self.webhook_secret = webhook_secret
        self.pending_jobs: Dict[str, asyncio.Future] = {}

    def verify_signature(self, payload: bytes, signature: str, timestamp: str) -> bool:
        """Verify webhook HMAC signature."""
        message = f"{payload.decode()}.{timestamp}"
        expected = hmac.new(
            self.webhook_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        received = signature.replace("sha256=", "")
        return hmac.compare_digest(expected, received)

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook notification."""
        payload = await request.read()
        signature = request.headers.get("X-Webhook-Signature", "")
        timestamp = request.headers.get("X-Webhook-Timestamp", "")

        # Verify signature
        if not self.verify_signature(payload, signature, timestamp):
            return web.Response(status=401, text="Invalid signature")

        data = json.loads(payload)
        job_id = data.get("job_id")

        # Resolve waiting future if exists
        if job_id in self.pending_jobs:
            self.pending_jobs[job_id].set_result(data)
            del self.pending_jobs[job_id]

        return web.Response(text="OK")

    async def wait_for_webhook(self, job_id: str, timeout: float = 60.0) -> Dict[str, Any]:
        """Wait for webhook notification for a specific job."""
        future = asyncio.Future()
        self.pending_jobs[job_id] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.pending_jobs.pop(job_id, None)


# Usage
async def extract_with_webhook():
    api = YouTubeSubtitleAPI(
        base_url="https://api.example.com",
        api_key="your_api_key"
    )
    webhook_handler = WebhookHandler(webhook_secret="your_webhook_secret")

    # Start webhook server (in a real app, this would run separately)
    app = web.Application()
    app.router.add_post("/webhook/subtitle", webhook_handler.handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()

    # Request extraction with webhook
    result = api.extract_subtitles(
        video_id="dQw4w9WgXcQ",
        webhook_url="https://your-app.com/webhook/subtitle"
    )

    # Wait for webhook notification
    if "job_id" in result:
        webhook_result = await webhook_handler.wait_for_webhook(result["job_id"])
        print(f"Got webhook: {webhook_result}")

    await runner.cleanup()
```

---

## JavaScript/Node.js Integration

### Basic Client

```javascript
class YouTubeSubtitleAPI {
  constructor(baseUrl, apiKey = null, timeout = 30000) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.timeout = timeout;
  }

  _headers() {
    const headers = { "Content-Type": "application/json" };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  async _fetch(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers: { ...this._headers(), ...options.headers },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || response.statusText);
      }
      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  async extractSubtitles({
    videoUrl = null,
    videoId = null,
    language = "en",
    cleanForAI = true,
    webhookUrl = null,
  } = {}) {
    const payload = { language, clean_for_ai: cleanForAI };

    if (videoUrl) payload.video_url = videoUrl;
    else if (videoId) payload.video_id = videoId;
    else throw new Error("Either videoUrl or videoId is required");

    if (webhookUrl) payload.webhook_url = webhookUrl;

    return this._fetch(`${this.baseUrl}/api/v1/subtitles`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getJobStatus(jobId) {
    return this._fetch(`${this.baseUrl}/api/v1/job/${jobId}`);
  }

  async waitForJob(jobId, maxWait = 60000, pollInterval = 1000) {
    const startTime = Date.now();

    while (Date.now() - startTime < maxWait) {
      const status = await this.getJobStatus(jobId);
      if (["finished", "failed", "not_found"].includes(status.status)) {
        return status;
      }
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }
    throw new Error(`Job ${jobId} did not complete within ${maxWait}ms`);
  }

  async extractAndWait(options, maxWait = 60000) {
    const result = await this.extractSubtitles(options);

    if (result.subtitles) return result;

    if (result.job_id) {
      const jobResult = await this.waitForJob(result.job_id, maxWait);
      if (jobResult.status === "finished" && jobResult.result) {
        return jobResult.result;
      }
      if (jobResult.status === "failed") {
        throw new Error(`Job failed: ${jobResult.exc_info}`);
      }
    }

    throw new Error("Unexpected response format");
  }
}

module.exports = YouTubeSubtitleAPI;
```

### Usage Examples

#### Basic Usage

```javascript
const API = require("./YouTubeSubtitleAPI");

async function main() {
  const api = new YouTubeSubtitleAPI(
    "https://api.example.com",
    "your_api_key_here", // Omit if no auth
  );

  try {
    const result = await api.extractAndWait({
      videoUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      language: "en",
    });

    console.log(`Title: ${result.title}`);
    console.log(`Subtitles: ${result.subtitle_count}`);
    console.log(`Text: ${result.plain_text.substring(0, 200)}...`);
  } catch (error) {
    console.error("Error:", error.message);
  }
}

main();
```

#### With Express Webhook Handler

```javascript
const express = require("express");
const crypto = require("crypto");
const YouTubeSubtitleAPI = require("./YouTubeSubtitleAPI");

const app = express();
app.use(express.json());

const api = new YouTubeSubtitleAPI("https://api.example.com", "your_api_key");
const WEBHOOK_SECRET = "your_webhook_secret";

function verifyWebhook(payload, signature, timestamp) {
  const message = `${payload}.${timestamp}`;
  const expected = crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(message)
    .digest("hex");
  const received = signature.replace("sha256=", "");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(received));
}

// Store pending job callbacks
const pendingJobs = new Map();

// Webhook endpoint
app.post("/webhook/subtitle", (req, res) => {
  const payload = JSON.stringify(req.body);
  const signature = req.get("X-Webhook-Signature");
  const timestamp = req.get("X-Webhook-Timestamp");

  if (!verifyWebhook(payload, signature, timestamp)) {
    return res.status(401).send("Invalid signature");
  }

  const { job_id, status, result, error } = req.body;

  // Resolve pending callback
  if (pendingJobs.has(job_id)) {
    const callback = pendingJobs.get(job_id);
    pendingJobs.delete(job_id);
    callback(req.body);
  }

  res.send("OK");
});

// Extract with webhook
function extractWithWebhook(videoId) {
  return new Promise((resolve, reject) => {
    // Set up callback
    const callback = (data) => {
      if (data.status === "success") resolve(data.result);
      else reject(new Error(data.error));
    };

    // Make request
    api
      .extractSubtitles({
        videoId,
        language: "en",
        webhookUrl: "https://your-app.com/webhook/subtitle",
      })
      .then((response) => {
        if (response.job_id) {
          pendingJobs.set(response.job_id, callback);
        } else if (response.subtitles) {
          resolve(response);
        }
      })
      .catch(reject);

    // Timeout after 60 seconds
    setTimeout(() => {
      if (pendingJobs.has(response?.job_id)) {
        pendingJobs.delete(response.job_id);
        reject(new Error("Webhook timeout"));
      }
    }, 60000);
  });
}

// Start server
app.listen(3000, () => console.log("Webhook server running on port 3000"));
```

---

## cURL Examples

### Basic Request

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'
```

### With API Key

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "language": "en"
  }'
```

### Batch Request

```bash
curl -X POST "https://api.example.com/api/v1/subtitles/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["dQw4w9WgXcQ", "anotherVideoId", "thirdVideoId"],
    "language": "en"
  }'
```

### Check Job Status

```bash
curl "https://api.example.com/api/v1/job/abc123-def456-ghi789"
```

### Get Cached Only

```bash
curl "https://api.example.com/api/v1/subtitles/dQw4w9WgXcQ?language=en"
```

### With Full Output (Debugging)

```bash
curl -v -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"video_id": "dQw4w9WgXcQ"}' \
  2>&1 | grep -E "(< HTTP|x-)"
```

---

## Error Handling Best Practices

### Python

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_resilient_session():
    """Create a session with automatic retries."""
    session = requests.Session()

    # Configure retry strategy
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

def extract_with_retry(api, video_id, max_retries=3):
    """Extract with custom retry logic for rate limits."""
    session = create_resilient_session()

    for attempt in range(max_retries):
        try:
            response = session.post(
                f"{api.base_url}/api/v1/subtitles",
                json={"video_id": video_id},
                headers=api._headers(),
                timeout=api.timeout
            )

            # Handle rate limiting
            if response.status_code == 429:
                data = response.json()
                retry_after = data.get("error", {}).get("meta", {}).get("retry_after", 60)
                print(f"Rate limited. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

        except requests.exceptions.HTTPError as e:
            print(f"HTTP error: {e}")
            if e.response.status_code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)

    raise Exception("Max retries exceeded")
```

### JavaScript

```javascript
class ResilientYouTubeAPI extends YouTubeSubtitleAPI {
  async extractWithRetry(options, maxRetries = 3) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const result = await this.extractSubtitles(options);

        // If we got a job_id, wait for completion
        if (result.job_id) {
          return await this.waitForJob(result.job_id);
        }
        return result;
      } catch (error) {
        const isRetryable =
          error.name === "AbortError" ||
          error.message?.includes("429") ||
          error.message?.includes("500") ||
          error.message?.includes("502");

        if (!isRetryable || attempt === maxRetries - 1) {
          throw error;
        }

        // Exponential backoff
        const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
        console.log(`Retry ${attempt + 1}/${maxRetries} after ${delay}ms`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  async extractWithRateLimitHandling(options) {
    try {
      return await this.extractWithRetry(options);
    } catch (error) {
      // Parse rate limit info from error
      if (error.message.includes("429")) {
        // Extract retry_after from error if available
        const retryMatch = error.message.match(/retry_after[":\s]+(\d+)/);
        const retryAfter = retryMatch ? parseInt(retryMatch[1]) * 1000 : 60000;

        console.log(`Rate limited. Retrying after ${retryAfter}ms...`);
        await new Promise((resolve) => setTimeout(resolve, retryAfter));
        return this.extractWithRetry(options);
      }
      throw error;
    }
  }
}
```

---

## Webhook Integration

### Webhook Payload Structure

#### Success Payload

```json
{
  "event": "job.completed",
  "job_id": "abc123-def456-ghi789",
  "video_id": "dQw4w9WgXcQ",
  "status": "success",
  "result": {
    "success": true,
    "video_id": "dQw4w9WgXcQ",
    "title": "Video Title",
    "language": "en",
    "subtitles": [...],
    "plain_text": "Full transcript..."
  },
  "timestamp": "2025-12-31T00:00:00Z"
}
```

#### Failure Payload

```json
{
  "event": "job.completed",
  "job_id": "abc123-def456-ghi789",
  "video_id": "dQw4w9WgXcQ",
  "status": "failed",
  "error": "Video unavailable or subtitles disabled",
  "timestamp": "2025-12-31T00:00:00Z"
}
```

### Webhook Best Practices

1. **Always verify signatures** - Use HMAC to verify webhook authenticity
2. **Return 2xx quickly** - Process asynchronously after acknowledging
3. **Handle retries** - Webhooks may be delivered multiple times (make idempotent)
4. **Log all webhooks** - Store for debugging and audit purposes
5. **Use HTTPS** - Never use HTTP for webhook URLs

---

## Rate Limit Handling

See [RATE_LIMITING.md](RATE_LIMITING.md) for complete details on rate limiting.

### Quick Tips

- Check `X-RateLimit-Remaining` header after each request
- Implement exponential backoff when receiving HTTP 429
- Use `Retry-After` header for precise wait time
- Consider caching results to reduce API calls

### Python Example

```python
def check_rate_limits(response):
    """Extract rate limit info from response headers."""
    return {
        "limit": int(response.headers.get("X-RateLimit-Limit", 0)),
        "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
        "reset": int(response.headers.get("X-RateLimit-Reset", 0))
    }

def wait_if_needed(response):
    """Wait if rate limit is approached."""
    limits = check_rate_limits(response)
    if limits["remaining"] < 5:
        wait_time = max(0, limits["reset"] - time.time()) + 1
        print(f"Approaching rate limit. Waiting {wait_time}s...")
        time.sleep(wait_time)
```

---

## Next Steps

- [USER_GUIDE.md](USER_GUIDE.md) - Getting started guide
- [ERROR_CODES.md](ERROR_CODES.md) - Error code reference
- [RATE_LIMITING.md](RATE_LIMITING.md) - Rate limiting details
- [API-README.md](API-README.md) - Complete API reference
