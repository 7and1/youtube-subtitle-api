/**
 * YouTube Subtitle API TypeScript SDK
 *
 * A type-safe, modern SDK for extracting YouTube subtitles with support for:
 * - Single and batch extraction
 * - Async job processing
 * - Webhook integration
 * - Multiple subtitle formats
 */

import {
  type Subtitle,
  type SubtitleItem,
  type ExtractSubtitlesOptions,
  type ExtractBatchOptions,
  type BatchExtractResponse,
  type JobStatusResponse,
  type JobStatus,
  type HealthResponse,
  type YouTubeSubtitleAPIConfig,
  type WaitForJobOptions,
  SubtitleFormat,
  type ExportOptions,
} from "./types.js";
import {
  YouTubeSubtitleAPIError,
  AuthenticationError,
  RateLimitError,
  NotFoundError,
  ValidationError,
  ServiceUnavailableError,
  TimeoutError,
  NetworkError,
  parseAPIError,
  isRetryableError,
} from "./errors.js";

/**
 * Default configuration values
 */
const DEFAULT_CONFIG = {
  baseUrl: "https://api.expertbeacon.com",
  timeout: 30000,
  maxRetries: 3,
  debug: false,
} as const;

/**
 * Extract video ID from various YouTube URL formats
 */
function extractVideoId(input: string): string {
  if (/^[a-zA-Z0-9_-]{11}$/.test(input)) {
    return input;
  }

  const patterns = [
    /(?:v=|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/,
    /(?:embed\/)([a-zA-Z0-9_-]{11})/,
    /(?:shorts\/)([a-zA-Z0-9_-]{11})/,
  ];

  for (const pattern of patterns) {
    const match = input.match(pattern);
    if (match) {
      return match[1];
    }
  }

  throw new ValidationError(
    "Invalid YouTube URL or video ID: " + input,
    "video_id",
  );
}

/**
 * Retry logic with exponential backoff
 */
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number,
  retryableCheck: (error: unknown) => boolean,
  debug?: boolean,
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt === maxRetries || !retryableCheck(error)) {
        throw error;
      }

      const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
      if (debug) {
        console.log(
          "Retrying after " +
            delay +
            "ms (attempt " +
            (attempt + 1) +
            "/" +
            maxRetries +
            ")",
        );
      }
      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * Sleep utility
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Main YouTube Subtitle API client class
 */
export class YouTubeSubtitleAPI {
  private readonly apiKey: string | undefined;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly debug: boolean;

  constructor(config: YouTubeSubtitleAPIConfig = {}) {
    this.apiKey = config.apiKey;
    this.baseUrl = (config.baseUrl || DEFAULT_CONFIG.baseUrl).replace(
      /\/$/,
      "",
    );
    this.timeout = config.timeout || DEFAULT_CONFIG.timeout;
    this.maxRetries = config.maxRetries ?? DEFAULT_CONFIG.maxRetries;
    this.debug = config.debug ?? DEFAULT_CONFIG.debug;

    if (this.debug) {
      console.log(
        "YouTubeSubtitleAPI initialized with baseUrl: " + this.baseUrl,
      );
    }
  }

  /**
   * Make an authenticated API request
   */
  private async request<T>(
    endpoint: string,
    options?: {
      method?: "GET" | "POST";
      body?: Record<string, unknown>;
      signal?: AbortSignal;
    },
  ): Promise<T> {
    const url = this.baseUrl + endpoint;

    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }

    if (this.debug) {
      console.log("Fetching: " + (options?.method || "GET") + " " + url);
    }

    const requestInit: RequestInit = {
      method: options?.method || "GET",
      headers,
      signal: options?.signal,
    };

    if (options?.body) {
      requestInit.body = JSON.stringify(options.body);
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    if (options?.signal) {
      options.signal.addEventListener("abort", () => controller.abort());
    }

    try {
      const response = await fetch(url, {
        ...requestInit,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorData: { detail?: string; code?: string } | undefined;
        try {
          errorData = await response.json();
        } catch {}

        throw parseAPIError(response, errorData);
      }

      return (await response.json()) as T;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof Error && error.name === "AbortError") {
        throw new TimeoutError("Request timeout after " + this.timeout + "ms");
      }

      throw error;
    }
  }

  /**
   * Extract subtitles from a YouTube video
   */
  async extractSubtitles(
    videoIdOrUrl: string,
    options: ExtractSubtitlesOptions = {},
  ): Promise<Subtitle> {
    const videoId = extractVideoId(videoIdOrUrl);
    const language = options.language ?? "en";
    const clean_for_ai = options.clean_for_ai ?? true;

    const response = await retryWithBackoff(
      () =>
        this.request<Subtitle>("/api/subtitles", {
          method: "POST",
          body: {
            video_id: videoId,
            language,
            clean_for_ai,
          },
        }),
      this.maxRetries,
      isRetryableError,
      this.debug,
    );

    return response;
  }

  /**
   * Get subtitles from a YouTube video (alias for extractSubtitles)
   */
  async getSubtitles(
    videoIdOrUrl: string,
    language: string = "en",
  ): Promise<Subtitle> {
    return this.extractSubtitles(videoIdOrUrl, { language });
  }

  /**
   * Get plain text transcript without timing data
   */
  async getTranscript(
    videoIdOrUrl: string,
    language: string = "en",
  ): Promise<string> {
    const result = await this.getSubtitles(videoIdOrUrl, language);
    return result.plain_text || "";
  }

  /**
   * Extract subtitles from multiple videos in batch
   */
  async extractBatch(
    videoIdsOrUrls: string[],
    options: ExtractBatchOptions = {},
  ): Promise<BatchExtractResponse> {
    const language = options.language ?? "en";
    const clean_for_ai = options.clean_for_ai ?? true;

    const results = await Promise.allSettled(
      videoIdsOrUrls.map((videoIdOrUrl) =>
        this.extractSubtitles(videoIdOrUrl, { language, clean_for_ai }),
      ),
    );

    const successful: Subtitle[] = [];
    const failed: string[] = [];

    for (let i = 0; i < results.length; i++) {
      if (results[i].status === "fulfilled") {
        successful.push(results[i].value);
      } else {
        failed.push(videoIdsOrUrls[i]);
      }
    }

    return {
      total: videoIdsOrUrls.length,
      successful: successful.length,
      failed: failed.length,
      results: successful,
    };
  }

  /**
   * Get the status of an async job
   */
  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>("/api/jobs/" + jobId);
  }

  /**
   * Wait for a job to complete
   */
  async waitForJob(
    jobId: string,
    options: WaitForJobOptions = {},
  ): Promise<JobStatusResponse> {
    const timeout = options.timeout ?? 60000;
    const pollInterval = options.pollInterval ?? 1000;
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const status = await this.getJobStatus(jobId);

      if (options.onProgress) {
        options.onProgress(status);
      }

      if (
        status.status === JobStatus.COMPLETED ||
        status.status === JobStatus.FAILED ||
        status.status === JobStatus.CANCELLED
      ) {
        return status;
      }

      await sleep(pollInterval);
    }

    throw new TimeoutError(
      "Job " + jobId + " did not complete within " + timeout + "ms",
    );
  }

  /**
   * Get API health status
   */
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  /**
   * Export subtitles to a specific format
   */
  exportSubtitles(subtitles: Subtitle, options: ExportOptions): string {
    switch (options.format) {
      case SubtitleFormat.SRT:
        return this.toSRT(subtitles.subtitles);
      case SubtitleFormat.VTT:
        return this.toVTT(subtitles.subtitles);
      case SubtitleFormat.TXT:
        return subtitles.plain_text || "";
      case SubtitleFormat.JSON:
        return JSON.stringify(subtitles, null, 2);
      default:
        throw new ValidationError("Unsupported format: " + options.format);
    }
  }

  /**
   * Convert subtitles to SRT format
   */
  private toSRT(subtitles: SubtitleItem[]): string {
    return subtitles
      .map((sub, index) => {
        const start = this.formatSRTTime(sub.start);
        const end = this.formatSRTTime(sub.start + sub.duration);
        return (
          index + 1 + "\n" + start + " --> " + end + "\n" + sub.text + "\n"
        );
      })
      .join("\n");
  }

  /**
   * Convert subtitles to VTT format
   */
  private toVTT(subtitles: SubtitleItem[]): string {
    const header = "WEBVTT\n\n";
    const body = subtitles
      .map((sub) => {
        const start = this.formatVTTTime(sub.start);
        const end = this.formatVTTTime(sub.start + sub.duration);
        return start + " --> " + end + "\n" + sub.text + "\n";
      })
      .join("\n");
    return header + body;
  }

  /**
   * Format time for SRT (HH:MM:SS,mmm)
   */
  private formatSRTTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.round((seconds % 1) * 1000);
    return (
      String(hours).padStart(2, "0") +
      ":" +
      String(minutes).padStart(2, "0") +
      ":" +
      String(secs).padStart(2, "0") +
      "," +
      String(ms).padStart(3, "0")
    );
  }

  /**
   * Format time for VTT (HH:MM:SS.mmm)
   */
  private formatVTTTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.round((seconds % 1) * 1000);
    return (
      String(hours).padStart(2, "0") +
      ":" +
      String(minutes).padStart(2, "0") +
      ":" +
      String(secs).padStart(2, "0") +
      "." +
      String(ms).padStart(3, "0")
    );
  }
}

/**
 * Create a new YouTube Subtitle API client (factory function)
 */
export function createClient(
  config: YouTubeSubtitleAPIConfig,
): YouTubeSubtitleAPI {
  return new YouTubeSubtitleAPI(config);
}

// Re-export types and errors for convenience
export * from "./types.js";
export * from "./errors.js";
export { verifySignature, parseWebhook } from "./webhook.js";
