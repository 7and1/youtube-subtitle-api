/**
 * Quick Start Example for YouTube Subtitle API SDK
 *
 * This example demonstrates the basic usage of the SDK.
 */

import { YouTubeSubtitleAPI, SubtitleFormat } from "../src/index.js";

// Initialize the client
const api = new YouTubeSubtitleAPI({
  apiKey: process.env.API_KEY,
  baseUrl: process.env.API_BASE_URL,
  debug: true,
});

async function main() {
  try {
    // Example 1: Get plain transcript
    console.log("\n=== Example 1: Get Plain Transcript ===");
    const transcript = await api.getTranscript("dQw4w9WgXcQ");
    console.log("Transcript preview:", transcript.slice(0, 200) + "...");

    // Example 2: Get full subtitle data with timing
    console.log("\n=== Example 2: Get Full Subtitle Data ===");
    const subtitles = await api.getSubtitles("dQw4w9WgXcQ", "en");
    console.log("Video ID:", subtitles.video_id);
    console.log("Title:", subtitles.title);
    console.log("Language:", subtitles.language);
    console.log("Subtitle count:", subtitles.subtitle_count);
    console.log("Extraction method:", subtitles.extraction_method);
    console.log("Cached:", subtitles.cached);

    // Example 3: Extract with options
    console.log("\n=== Example 3: Extract with Options ===");
    const result = await api.extractSubtitles(
      "https://youtube.com/watch?v=dQw4w9WgXcQ",
      {
        language: "en",
        clean_for_ai: true,
      },
    );
    console.log("Subtitles extracted:", result.subtitle_count, "items");

    // Example 4: Export to SRT format
    console.log("\n=== Example 4: Export to SRT ===");
    const srt = api.exportSubtitles(subtitles, { format: SubtitleFormat.SRT });
    console.log("SRT preview:\n", srt.slice(0, 300) + "...");

    // Example 5: Export to VTT format
    console.log("\n=== Example 5: Export to VTT ===");
    const vtt = api.exportSubtitles(subtitles, { format: SubtitleFormat.VTT });
    console.log("VTT preview:\n", vtt.slice(0, 300) + "...");

    // Example 6: Batch extraction
    console.log("\n=== Example 6: Batch Extraction ===");
    const batchResult = await api.extractBatch(["dQw4w9WgXcQ", "9bZkp7q19f0"], {
      language: "en",
    });
    console.log("Batch results:");
    console.log("  Total:", batchResult.total);
    console.log("  Successful:", batchResult.successful);
    console.log("  Failed:", batchResult.failed);

    // Example 7: Check API health
    console.log("\n=== Example 7: API Health ===");
    const health = await api.getHealth();
    console.log("API Status:", health.status);
    console.log("Cache size:", health.cache_size);
    console.log("Cache hit rate:", health.cache_hit_rate);
    console.log("Uptime:", health.uptime_seconds, "seconds");
  } catch (error) {
    if (error instanceof Error) {
      console.error("Error:", error.name, "-", error.message);
    } else {
      console.error("Unknown error:", error);
    }
  }
}

// Run the examples
main().catch(console.error);
