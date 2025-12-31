# @youtube-subtitle-api/sdk

TypeScript SDK for the YouTube Subtitle API - Extract subtitles from YouTube videos with ease.

## Features

- Type-safe TypeScript SDK with full ESM and CJS support
- Extract subtitles in multiple languages
- Export to SRT, VTT, TXT, and JSON formats
- Batch extraction support
- Async job processing with webhooks
- Automatic retry with exponential backoff
- Comprehensive error handling
- Node.js 18+ and browser support

## Installation

```bash
npm install @youtube-subtitle-api/sdk
# or
yarn add @youtube-subtitle-api/sdk
# or
pnpm add @youtube-subtitle-api/sdk
```

## Quick Start

```typescript
import { YouTubeSubtitleAPI, SubtitleFormat } from "@youtube-subtitle-api/sdk";

// Initialize the client
const api = new YouTubeSubtitleAPI({
  apiKey: process.env.API_KEY, // Optional
});

// Get subtitles
const subtitles = await api.getSubtitles("dQw4w9WgXcQ", "en");
console.log(subtitles.plain_text);

// Export to SRT format
const srt = api.exportSubtitles(subtitles, { format: SubtitleFormat.SRT });
console.log(srt);
```

## Configuration

```typescript
import { YouTubeSubtitleAPI } from "@youtube-subtitle-api/sdk";

const api = new YouTubeSubtitleAPI({
  apiKey: "your-api-key", // Optional API key
  baseUrl: "https://api...", // Custom base URL
  timeout: 60000, // Request timeout (ms)
  maxRetries: 3, // Max retry attempts
  debug: true, // Enable debug logging
});
```

## Methods

### `getSubtitles(videoId, language)`

Extract subtitles from a YouTube video.

```typescript
const subtitles = await api.getSubtitles("dQw4w9WgXcQ", "en");

console.log(subtitles.video_id); // 'dQw4w9WgXcQ'
console.log(subtitles.title); // Video title
console.log(subtitles.language); // 'en'
console.log(subtitles.subtitle_count); // Number of items
console.log(subtitles.subtitles); // Array of subtitle items
console.log(subtitles.plain_text); // Full transcript
```

### `getTranscript(videoId, language)`

Get plain text transcript without timing data.

```typescript
const transcript = await api.getTranscript("dQw4w9WgXcQ", "en");
console.log(transcript);
```

### `extractSubtitles(videoIdOrUrl, options)`

Extract with additional options.

```typescript
const result = await api.extractSubtitles(
  "https://youtube.com/watch?v=dQw4w9WgXcQ",
  {
    language: "en",
    clean_for_ai: true, // Clean VTT formatting
  },
);
```

### `extractBatch(videoIds, options)`

Extract subtitles from multiple videos.

```typescript
const result = await api.extractBatch(["dQw4w9WgXcQ", "9bZkp7q19f0"], {
  language: "en",
});

console.log(`Extracted ${result.successful} of ${result.total} videos`);
console.log(result.results); // Array of successful extractions
```

### `getJobStatus(jobId)`

Get the status of an async job.

```typescript
const status = await api.getJobStatus("job_abc123");
console.log(status.status); // 'pending' | 'processing' | 'completed' | 'failed'
```

### `waitForJob(jobId, options)`

Wait for a job to complete with polling.

```typescript
const result = await api.waitForJob("job_abc123", {
  timeout: 60000, // Max wait time (ms)
  pollInterval: 1000, // Poll interval (ms)
  onProgress: (status) => {
    console.log(`Progress: ${status.progress}%`);
  },
});
```

### `getHealth()`

Check API health status.

```typescript
const health = await api.getHealth();
console.log(health.status); // 'healthy'
console.log(health.cache_hit_rate); // Cache efficiency
console.log(health.uptime_seconds); // Server uptime
```

### `exportSubtitles(subtitles, options)`

Export subtitles to various formats.

```typescript
// SRT format
const srt = api.exportSubtitles(subtitles, { format: SubtitleFormat.SRT });

// VTT format
const vtt = api.exportSubtitles(subtitles, { format: SubtitleFormat.VTT });

// Plain text
const txt = api.exportSubtitles(subtitles, { format: SubtitleFormat.TXT });

// JSON
const json = api.exportSubtitles(subtitles, { format: SubtitleFormat.JSON });
```

## Error Handling

The SDK provides specific error types for different scenarios:

```typescript
import {
  AuthenticationError,
  RateLimitError,
  NotFoundError,
  ValidationError,
  TimeoutError,
} from "@youtube-subtitle-api/sdk";

try {
  const subtitles = await api.getSubtitles("dQw4w9WgXcQ");
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error("Invalid API key");
  } else if (error instanceof RateLimitError) {
    console.error("Rate limited - retry after:", error.retryAfter);
  } else if (error instanceof NotFoundError) {
    console.error("Video not found");
  } else if (error instanceof ValidationError) {
    console.error("Invalid input:", error.field);
  } else if (error instanceof TimeoutError) {
    console.error("Request timed out");
  }
}
```

## Webhooks

Handle webhook notifications for async operations:

```typescript
import {
  verifySignature,
  parseWebhook,
} from "@youtube-subtitle-api/sdk/webhook";

// Verify webhook signature
function handleWebhook(rawBody: string, signature: string) {
  if (!verifySignature(rawBody, signature, process.env.WEBHOOK_SECRET)) {
    throw new Error("Invalid signature");
  }

  const payload = parseWebhook(rawBody);
  console.log("Event:", payload.event);
  console.log("Job ID:", payload.job_id);
}
```

### Webhook Server Example

```typescript
import { createWebhookHandler } from "@youtube-subtitle-api/sdk/webhook";
import express from "express";

const app = express();
app.use(express.raw({ type: "application/json" }));

const handler = createWebhookHandler({
  secret: process.env.WEBHOOK_SECRET,
  onSubtitleCompleted: (result) => {
    console.log("Subtitles extracted:", result.video_id);
  },
  onSubtitleFailed: (error) => {
    console.error("Extraction failed:", error.job_id);
  },
});

app.post("/webhook", async (req, res) => {
  const response = await handler({
    body: req.body,
    headers: req.headers,
  });
  res.status(response.status).send(await response.text());
});

app.listen(3000);
```

## Types

### `Subtitle`

```typescript
interface Subtitle {
  success: boolean;
  video_id: string;
  title?: string;
  language: string;
  extraction_method: string;
  subtitle_count: number;
  duration_ms: number;
  cached: boolean;
  subtitles: SubtitleItem[];
  plain_text?: string;
  proxy_used?: string;
}
```

### `SubtitleItem`

```typescript
interface SubtitleItem {
  start: number; // Start time in seconds
  duration: number; // Duration in seconds
  text: string; // Subtitle text
}
```

### `JobStatus`

```typescript
enum JobStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}
```

## License

MIT

## Support

For issues and feature requests, visit: https://github.com/expertbeacon/youtube-subtitle-api
