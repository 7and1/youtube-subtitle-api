/**
 * Advanced Usage Examples
 *
 * This example demonstrates advanced features of the SDK.
 */

import {
  YouTubeSubtitleAPI,
  SubtitleFormat,
  JobStatus,
  type YouTubeSubtitleAPIConfig,
} from "../src/index.js";

// Advanced client configuration
const config: YouTubeSubtitleAPIConfig = {
  apiKey: process.env.API_KEY,
  baseUrl: process.env.API_BASE_URL,
  timeout: 60000, // 60 seconds
  maxRetries: 5,
  debug: true,
};

const api = new YouTubeSubtitleAPI(config);

/**
 * Example 1: Extract with custom timeout and retry
 */
async function extractWithRetry(videoId: string) {
  console.log("\n=== Extract with Custom Retry ===");

  try {
    const result = await api.extractSubtitles(videoId, {
      language: "en",
      clean_for_ai: true,
    });
    console.log("Success:", result.title);
    return result;
  } catch (error) {
    if (error instanceof Error) {
      console.error("Failed after retries:", error.message);
    }
    throw error;
  }
}

/**
 * Example 2: Process multiple videos with concurrency control
 */
async function processBatch(videoIds: string[], concurrency: number = 3) {
  console.log("\n=== Batch Processing with Concurrency Control ===");

  const results: Array<{
    id: string;
    success: boolean;
    data?: any;
    error?: string;
  }> = [];

  for (let i = 0; i < videoIds.length; i += concurrency) {
    const batch = videoIds.slice(i, i + concurrency);
    const batchResults = await Promise.allSettled(
      batch.map((id) => api.getSubtitles(id)),
    );

    for (let j = 0; j < batch.length; j++) {
      const result = batchResults[j];
      if (result.status === "fulfilled") {
        results.push({ id: batch[j], success: true, data: result.value });
      } else {
        results.push({
          id: batch[j],
          success: false,
          error:
            result.reason instanceof Error
              ? result.reason.message
              : "Unknown error",
        });
      }
    }
  }

  console.log("Processed:", results.length);
  console.log("Successful:", results.filter((r) => r.success).length);
  console.log("Failed:", results.filter((r) => !r.success).length);

  return results;
}

/**
 * Example 3: Export to multiple formats
 */
async function exportToMultipleFormats(videoId: string) {
  console.log("\n=== Export to Multiple Formats ===");

  const subtitles = await api.getSubtitles(videoId);

  const formats = [
    SubtitleFormat.SRT,
    SubtitleFormat.VTT,
    SubtitleFormat.TXT,
    SubtitleFormat.JSON,
  ];

  const exports = formats.map((format) => ({
    format,
    content: api.exportSubtitles(subtitles, { format }),
  }));

  for (const exp of exports) {
    const size = exp.content.length;
    console.log("Format: " + exp.format + ", Size: " + size + " bytes");
  }

  return exports;
}

/**
 * Example 4: Search subtitle text
 */
async function searchInSubtitles(videoId: string, searchTerm: string) {
  console.log("\n=== Search in Subtitles ===");

  const subtitles = await api.getSubtitles(videoId);

  const matches = subtitles.subtitles.filter((item) =>
    item.text.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  console.log("Found " + matches.length + ' matches for "' + searchTerm + '":');
  for (const match of matches.slice(0, 5)) {
    const timestamp = formatTimestamp(match.start);
    console.log("  [" + timestamp + "] " + match.text);
  }

  return matches;
}

/**
 * Format timestamp as HH:MM:SS
 */
function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const pad = (n: number) => String(n).padStart(2, "0");
  return pad(h) + ":" + pad(m) + ":" + pad(s);
}

/**
 * Example 5: Extract word-by-word timing
 */
async function getWordTiming(videoId: string) {
  console.log("\n=== Word Timing Analysis ===");

  const subtitles = await api.getSubtitles(videoId);

  const words: Array<{ word: string; start: number; end: number }> = [];

  for (const item of subtitles.subtitles) {
    const itemWords = item.text.split(/\s+/);
    const durationPerWord = item.duration / itemWords.length;

    itemWords.forEach((word, i) => {
      words.push({
        word,
        start: item.start + i * durationPerWord,
        end: item.start + (i + 1) * durationPerWord,
      });
    });
  }

  console.log("Total words:", words.length);
  console.log("Sample timing:", words.slice(0, 5));

  return words;
}

/**
 * Example 6: Wait for async job with progress
 */
async function waitForJobWithProgress(jobId: string) {
  console.log("\n=== Wait for Job with Progress ===");

  const result = await api.waitForJob(jobId, {
    timeout: 120000, // 2 minutes
    pollInterval: 2000, // 2 seconds
    onProgress: (status) => {
      const progress = status.progress ?? 0;
      console.log("Progress: " + status.status + " (" + progress + "%)");
    },
  });

  console.log("Job completed:", result.status);

  return result;
}

/**
 * Example 7: Custom error handling
 */
async function extractWithErrorHandling(videoId: string) {
  console.log("\n=== Custom Error Handling ===");

  try {
    const result = await api.getSubtitles(videoId);
    return result;
  } catch (error) {
    // Handle specific error types
    if (error instanceof Error) {
      switch (error.constructor.name) {
        case "AuthenticationError":
          console.error("API key is invalid");
          break;
        case "RateLimitError":
          console.error("Rate limited - please wait");
          break;
        case "NotFoundError":
          console.error("Video or subtitles not found");
          break;
        case "ValidationError":
          console.error("Invalid input:", error.message);
          break;
        case "TimeoutError":
          console.error("Request timed out");
          break;
        default:
          console.error("Unexpected error:", error.message);
      }
    }
    throw error;
  }
}

// Run all examples
async function main() {
  const videoId = "dQw4w9WgXcQ";

  try {
    await extractWithRetry(videoId);
    await processBatch([videoId, "9bZkp7q19f0"], 2);
    await exportToMultipleFormats(videoId);
    await searchInSubtitles(videoId, "never");
    await getWordTiming(videoId);
    await extractWithErrorHandling(videoId);
  } catch (error) {
    console.error("Example failed:", error);
  }
}

main().catch(console.error);
