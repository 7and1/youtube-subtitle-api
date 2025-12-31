# YouTube Subtitle API - Rate Limiting Guide

**Version:** 1.0.0 | **Last Updated:** 2025-12-31

This guide explains how rate limiting works and provides best practices for handling rate limits.

## Table of Contents

- [How Rate Limits Work](#how-rate-limits-work)
- [Rate Limit Headers](#rate-limit-headers)
- [Handling 429 Responses](#handling-429-responses)
- [Best Practices](#best-practices)
- [Requesting Higher Limits](#requesting-higher-limits)
- [Code Examples](#code-examples)

---

## How Rate Limits Work

### Token Bucket Algorithm

The API uses a **token bucket algorithm** for rate limiting:

- **Base rate:** 30 requests per minute (default)
- **Burst allowance:** 5 additional requests
- **Total capacity:** 35 requests
- **Refill rate:** 0.5 requests per second

### How It Works

```
Initial State:   [####################] 35 tokens

Request 1:       [###################-] 34 tokens
Request 2:       [##################--] 33 tokens
...
Request 30:      [#####---------------] 5 tokens (burst remaining)
Request 31:      [####----------------] 4 tokens
...
Request 35:      [--------------------] 0 tokens (LIMITED)

After 2 seconds: [#-------------------] 1 token (refilled)
After 60 seconds: [####################] 35 tokens (full refill)
```

### Key Concepts

| Concept                 | Description                                  |
| ----------------------- | -------------------------------------------- |
| **Requests per minute** | Base sustained rate (30 req/min)             |
| **Burst size**          | Additional capacity for short spikes (5 req) |
| **Capacity**            | Total tokens = base + burst (35)             |
| **Refill rate**         | Tokens regenerated per second (0.5/sec)      |
| **Per-IP limiting**     | Limits apply per client IP address           |

### Why Token Bucket?

- Allows bursts for real-time use cases
- Fair allocation across all users
- Prevents abuse while accommodating legitimate traffic patterns
- Industry-standard approach

---

## Rate Limit Headers

Every API response includes rate limit information in the headers:

### Header Format

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1735629600
X-RateLimit-Policy: 30;w=60;burst=5
```

### Header Definitions

| Header                  | Type      | Description                                       |
| ----------------------- | --------- | ------------------------------------------------- |
| `X-RateLimit-Limit`     | number    | Base requests per minute (30)                     |
| `X-RateLimit-Remaining` | number    | Remaining requests in current window              |
| `X-RateLimit-Reset`     | timestamp | Unix timestamp when limit resets                  |
| `X-RateLimit-Policy`    | string    | Policy format: `{limit};w={window};burst={burst}` |

### Policy Format Breakdown

```
30;w=60;burst=5
  |  |    |
  |  |    +-- Burst size (additional requests)
  |  +------- Window in seconds (60 seconds = 1 minute)
  +---------- Base limit (30 requests)
```

### Reading the Headers

```bash
# Make a request and show headers
curl -i "https://api.example.com/api/v1/subtitles/dQw4w9WgXcQ"
```

**Response:**

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 29
X-RateLimit-Reset: 1735629660
X-RateLimit-Policy: 30;w=60;burst=5
```

This means:

- You have 30 requests per minute base limit
- You have 29 requests remaining
- The limit resets at Unix timestamp 1735629660
- You have a burst capacity of 5 additional requests

---

## Handling 429 Responses

When you exceed the rate limit, you receive HTTP 429:

### Error Response

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

### Response Headers

```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1735629600
```

### Handling Strategies

#### 1. Use Retry-After Header

The `Retry-After` header tells you exactly how long to wait:

```python
import requests
import time

def make_request_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            continue

        response.raise_for_status()
        return response

    raise Exception("Max retries exceeded")
```

#### 2. Parse Error Meta

```python
def handle_rate_limit_error(response):
    if response.status_code == 429:
        error_data = response.json()
        retry_after = error_data.get("error", {}).get("meta", {}).get("retry_after", 60)
        reset_at = error_data.get("error", {}).get("meta", {}).get("reset_at")
        print(f"Rate limited until {reset_at}")
        print(f"Retry after {retry_after} seconds")
        return retry_after
    return 0
```

#### 3. Exponential Backoff

When retry_after is not available, use exponential backoff:

```python
import time

def request_with_backoff(func, max_retries=5):
    for attempt in range(max_retries):
        try:
            return func()
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = min(2 ** attempt, 60)  # Cap at 60 seconds
                print(f"Attempt {attempt + 1}: waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")
```

---

## Best Practices

### 1. Check Headers Before Requesting

```python
class RateLimitAwareClient:
    def __init__(self):
        self.remaining = 30
        self.reset_time = None

    def update_limit(self, response):
        self.remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        self.reset_time = int(response.headers.get("X-RateLimit-Reset", 0))

    def should_wait(self):
        if self.remaining <= 5:
            if self.reset_time:
                wait_seconds = self.reset_time - time.time() + 1
                if wait_seconds > 0:
                    return wait_seconds
        return 0

    def request(self, url):
        wait = self.should_wait()
        if wait > 0:
            print(f"Approaching limit. Waiting {wait}s...")
            time.sleep(wait)

        response = requests.get(url)
        self.update_limit(response)
        return response
```

### 2. Implement Request Queuing

```python
import asyncio
from asyncio import Queue

class RateLimitedQueue:
    def __init__(self, rate_limit=30, window=60):
        self.rate_limit = rate_limit
        self.window = window
        self.requests = []
        self.queue = Queue()

    async def acquire(self):
        now = time.time()
        # Remove old requests outside the window
        self.requests = [t for t in self.requests if t > now - self.window]

        if len(self.requests) >= self.rate_limit:
            # Wait until the oldest request expires
            wait_time = self.requests[0] + self.window - now
            await asyncio.sleep(wait_time)
            return await self.acquire()

        self.requests.append(now)
        return True

# Usage
async def make_request(url):
    await queue.acquire()
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### 3. Use Batching Efficiently

Instead of individual requests, use the batch endpoint:

```python
# Bad: 10 individual requests
for video_id in video_ids:
    api.extract_subtitles(video_id=video_id)

# Good: 1 batch request
api.extract_batch(video_ids=video_ids)
```

### 4. Cache Results Aggressively

```python
from functools import lru_cache
import time

class CachedSubtitleAPI:
    def __init__(self, api, ttl=3600):
        self.api = api
        self.cache = {}
        self.ttl = ttl

    def extract_subtitles(self, video_id, language="en"):
        cache_key = f"{video_id}:{language}"
        now = time.time()

        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if now - timestamp < self.ttl:
                print("Cache hit!")
                return data

        result = self.api.extract_subtitles(video_id=video_id, language=language)
        self.cache[cache_key] = (result, now)
        return result
```

### 5. Monitor Rate Limits in Production

```python
class RateLimitMonitor:
    def __init__(self):
        self.requests_made = 0
        self.rate_limit_hits = 0
        self.start_time = time.time()

    def log_request(self, response):
        self.requests_made += 1

        remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        if remaining == 0:
            self.rate_limit_hits += 1

        if self.requests_made % 100 == 0:
            self.report()

    def report(self):
        elapsed = time.time() - self.start_time
        rate = self.requests_made / elapsed * 60  # per minute
        print(f"Rate: {rate:.1f} req/min | Hits: {self.rate_limit_hits}")
```

---

## Requesting Higher Limits

### Current Limits

| Plan    | Requests/Minute | Burst | Cost          |
| ------- | --------------- | ----- | ------------- |
| Default | 30              | 5     | Contact sales |

### When to Request Higher Limits

Consider higher limits if you need to:

- Process more than 30 videos per minute
- Support multiple concurrent users
- Build high-volume batch processing pipelines
- Provide real-time subtitle extraction

### How to Request

1. **Document your use case:**
   - Expected request volume per day/week
   - Number of users/concurrent connections
   - Business justification

2. **Contact support:**
   - Include your API key or account ID
   - Provide the documentation above
   - Allow 1-2 business days for review

3. **Implementation:**
   - Higher limits are configured server-side
   - Your `X-RateLimit-Limit` header will reflect new limits
   - No code changes required

### Alternative Strategies

If higher limits aren't available:

- **Implement caching** to reduce redundant requests
- **Use batch endpoints** to process multiple videos per request
- **Schedule processing** during off-peak hours
- **Distribute load** across multiple API keys (if allowed)

---

## Code Examples

### Python: Retry Decorator

```python
import time
import functools
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def retry_on_rate_limit(max_retries=5, base_delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    if e.response.status_code == 429:
                        # Use Retry-After header if available
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after:
                            delay = int(retry_after)
                        else:
                            delay = base_delay * (2 ** attempt)

                        if attempt < max_retries - 1:
                            print(f"Rate limited. Retry in {delay}s...")
                            time.sleep(delay)
                        else:
                            raise
                    else:
                        raise
            return None
        return wrapper
    return decorator

# Usage
@retry_on_rate_limit(max_retries=5)
def extract_with_retry(video_id):
    response = requests.post(
        "https://api.example.com/api/v1/subtitles",
        json={"video_id": video_id}
    )
    response.raise_for_status()
    return response.json()
```

### JavaScript: Rate Limiter Class

```javascript
class RateLimiter {
  constructor(requestsPerMinute = 30) {
    this.requestsPerMinute = requestsPerMinute;
    this.requests = [];
  }

  async acquire() {
    const now = Date.now();
    const windowMs = 60000; // 1 minute

    // Remove old requests outside the window
    this.requests = this.requests.filter((t) => t > now - windowMs);

    // Check if we need to wait
    if (this.requests.length >= this.requestsPerMinute) {
      const oldestRequest = this.requests[0];
      const waitTime = oldestRequest + windowMs - now;

      if (waitTime > 0) {
        console.log(`Rate limited. Waiting ${waitTime}ms...`);
        await new Promise((resolve) => setTimeout(resolve, waitTime));
        return this.acquire();
      }
    }

    this.requests.push(now);
    return true;
  }
}

class RateLimitedAPI {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
    this.limiter = new RateLimiter(30);
  }

  async extractSubtitles(videoId) {
    await this.limiter.acquire();

    const response = await fetch(`${this.baseUrl}/api/v1/subtitles`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
      },
      body: JSON.stringify({ video_id: videoId }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || response.statusText);
    }

    return await response.json();
  }
}
```

### Go: Token Bucket Implementation

```go
package main

import (
    "net/http"
    "time"
)

type TokenBucket struct {
    capacity    int
    tokens      int
    refillRate  time.Duration
    lastRefill  time.Time
}

func NewTokenBucket(capacity int, refillRate time.Duration) *TokenBucket {
    return &TokenBucket{
        capacity:   capacity,
        tokens:     capacity,
        refillRate: refillRate,
        lastRefill: time.Now(),
    }
}

func (tb *TokenBucket) refill() {
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill)

    // Add tokens based on elapsed time
    tokensToAdd := int(elapsed / tb.refillRate)
    if tokensToAdd > 0 {
        tb.tokens = min(tb.capacity, tb.tokens+tokensToAdd)
        tb.lastRefill = now
    }
}

func (tb *TokenBucket) Acquire() bool {
    tb.refill()

    if tb.tokens > 0 {
        tb.tokens--
        return true
    }

    return false
}

func (tb *TokenBucket) Wait() {
    for !tb.Acquire() {
        time.Sleep(tb.refillRate)
    }
}

// Usage
type RateLimitedClient struct {
    bucket *TokenBucket
    client *http.Client
}

func (c *RateLimitedClient) Get(url string) (*http.Response, error) {
    c.bucket.Wait()
    return c.client.Get(url)
}
```

---

## Next Steps

- [USER_GUIDE.md](USER_GUIDE.md) - Getting started guide
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Integration examples
- [ERROR_CODES.md](ERROR_CODES.md) - Error code reference
- [API-README.md](API-README.md) - Complete API reference
