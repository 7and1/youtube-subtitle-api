/**
 * TypeScript types for YouTube Subtitle API SDK
 */

/**
 * Individual subtitle item with timing information
 */
export interface SubtitleItem {
  /** Start time in seconds */
  start: number;
  /** Duration in seconds */
  duration: number;
  /** Subtitle text content */
  text: string;
}

/**
 * Subtitle extraction response
 */
export interface Subtitle {
  /** Whether the extraction was successful */
  success: boolean;
  /** YouTube video ID (11 characters) */
  video_id: string;
  /** Video title (if available) */
  title?: string;
  /** Language code of the extracted subtitles */
  language: string;
  /** Method used for extraction ("youtube-transcript-api" or "yt-dlp") */
  extraction_method: string;
  /** Number of subtitle items extracted */
  subtitle_count: number;
  /** Extraction duration in milliseconds */
  duration_ms: number;
  /** Whether the result was from cache */
  cached: boolean;
  /** Array of subtitle items with timing */
  subtitles: SubtitleItem[];
  /** Plain text transcript (concatenated subtitles) */
  plain_text?: string;
  /** Proxy used for extraction (if applicable) */
  proxy_used?: string;
}

/**
 * Request options for subtitle extraction
 */
export interface ExtractSubtitlesOptions {
  /** Preferred subtitle language code (default: "en") */
  language?: string;
  /** Whether to clean VTT formatting for AI consumption (default: true) */
  clean_for_ai?: boolean;
  /** Optional webhook URL for async processing */
  webhook_url?: string;
}

/**
 * Batch extraction request options
 */
export interface ExtractBatchOptions {
  /** Preferred subtitle language code (default: "en") */
  language?: string;
  /** Whether to clean VTT formatting for AI consumption (default: true) */
  clean_for_ai?: boolean;
  /** Optional webhook URL for async processing */
  webhook_url?: string;
}

/**
 * Batch extraction response
 */
export interface BatchExtractResponse {
  /** Number of videos in batch */
  total: number;
  /** Number of successful extractions */
  successful: number;
  /** Number of failed extractions */
  failed: number;
  /** Array of extraction results */
  results: Subtitle[];
}

/**
 * Job status for async operations
 */
export enum JobStatus {
  /** Job is pending */
  PENDING = "pending",
  /** Job is currently processing */
  PROCESSING = "processing",
  /** Job completed successfully */
  COMPLETED = "completed",
  /** Job failed */
  FAILED = "failed",
  /** Job was cancelled */
  CANCELLED = "cancelled",
}

/**
 * Job status response
 */
export interface JobStatusResponse {
  /** Unique job identifier */
  job_id: string;
  /** Current job status */
  status: JobStatus;
  /** YouTube video ID */
  video_id?: string;
  /** Extraction result (if completed) */
  result?: Subtitle;
  /** Error message (if failed) */
  error?: string;
  /** Job creation timestamp */
  created_at: string;
  /** Job completion timestamp (if completed) */
  completed_at?: string;
  /** Progress percentage (0-100) */
  progress?: number;
}

/**
 * Health check response
 */
export interface HealthResponse {
  /** Service status */
  status: string;
  /** Current cache size */
  cache_size: number;
  /** Cache hit rate (0-1) */
  cache_hit_rate: number;
  /** Service uptime in seconds */
  uptime_seconds: number;
  /** Proxy pool statistics (if available) */
  proxy_stats?: ProxyStats;
}

/**
 * Proxy pool statistics
 */
export interface ProxyStats {
  /** Total number of proxies */
  total: number;
  /** Number of active proxies */
  active: number;
  /** Number of failed proxies */
  failed: number;
  /** Proxy success rate */
  success_rate: number;
}

/**
 * API error response
 */
export interface ErrorResponse {
  /** Error detail message */
  detail: string;
  /** Optional error code */
  code?: string;
  /** HTTP status code */
  status?: number;
}

/**
 * Webhook payload types
 */
export interface WebhookPayload {
  /** Event type */
  event: "subtitle.completed" | "subtitle.failed" | "batch.completed";
  /** Job ID */
  job_id: string;
  /** Timestamp */
  timestamp: string;
  /** Data (varies by event type) */
  data: Subtitle | BatchExtractResponse;
  /** Signature for verification */
  signature?: string;
}

/**
 * SDK configuration options
 */
export interface YouTubeSubtitleAPIConfig {
  /** API key for authentication */
  apiKey?: string;
  /** Base URL of the API (default: official API URL) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 30000) */
  timeout?: number;
  /** Maximum number of retries (default: 3) */
  maxRetries?: number;
  /** Enable debug logging (default: false) */
  debug?: boolean;
}

/**
 * Wait for job completion options
 */
export interface WaitForJobOptions {
  /** Maximum time to wait in milliseconds (default: 60000) */
  timeout?: number;
  /** Polling interval in milliseconds (default: 1000) */
  pollInterval?: number;
  /** Callback function called on each poll with current status */
  onProgress?: (status: JobStatusResponse) => void;
}

/**
 * Subtitle format for export
 */
export enum SubtitleFormat {
  /** SubRip format */
  SRT = "srt",
  /** WebVTT format */
  VTT = "vtt",
  /** Plain text format */
  TXT = "txt",
  /** JSON format */
  JSON = "json",
}

/**
 * Export options
 */
export interface ExportOptions {
  /** Output format */
  format: SubtitleFormat;
  /** Include timestamps (ignored for TXT and JSON) */
  includeTimestamps?: boolean;
}
