# YouTube Subtitle API

Dual-engine YouTube subtitle extraction service for AI consumption.

## Quick Start

```bash
# 1. Initialize
make init

# 2. Configure API key
vim .env  # Set API_KEY

# 3. Deploy
make deploy

# 4. Test
curl http://localhost:8020/health
```

## API Endpoints

### Health Check

```bash
GET /health
```

### Extract Subtitles

```bash
POST /api/subtitles
Content-Type: application/json
X-API-Key: your-api-key

{
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "clean_for_ai": true
}
```

Or with URL:

```bash
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "en"
}
```

### Response Format

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "language": "en",
  "extraction_method": "youtube-transcript-api",
  "subtitle_count": 42,
  "duration_ms": 1234,
  "cached": false,
  "subtitles": [
    { "start": 0.5, "duration": 2.0, "text": "We are no strangers to love" }
  ],
  "plain_text": "We are no strangers to love You know the rules..."
}
```

## Architecture

```
Client Request
      |
      v
+------------------+
| FastAPI Service  |
| - Rate limiting  |
| - API key auth   |
| - In-memory cache|
+--------+---------+
         |
    +----+----+
    |         |
    v         v
+-------+  +------+
| YT-API|  |yt-dlp|
| (fast)|  |(fallback)
+-------+  +------+
```

## Configuration

| Variable              | Default | Description                               |
| --------------------- | ------- | ----------------------------------------- |
| API_KEY               | ""      | API key for authentication (empty = open) |
| ALLOWED_ORIGINS       | \*      | CORS allowed origins                      |
| RATE_LIMIT_PER_MINUTE | 30      | Max requests per IP per minute            |
| MAX_CONCURRENT        | 5       | Max concurrent extractions                |
| CACHE_TTL_SECONDS     | 3600    | Cache TTL (1 hour)                        |
| CACHE_MAX_SIZE        | 500     | Max cached videos                         |
| EXTRACTION_TIMEOUT    | 30      | Timeout per extraction (seconds)          |
| FALLBACK_ENABLED      | true    | Enable yt-dlp fallback                    |

## Commands

```bash
make help      # Show all commands
make init      # Initialize .env
make build     # Build image
make deploy    # Deploy container
make logs      # View logs
make down      # Stop container
make health    # Check health
make test      # Test extraction
```

## Resource Limits

- Memory: 512MB max / 256MB reserved
- CPU: 1 core max
- Port: 8020 (external) -> 8000 (internal)

## Network

Connected to `nginx-proxy_default` for optional subdomain routing.
