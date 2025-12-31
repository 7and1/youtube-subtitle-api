/**
 * Custom error classes for YouTube Subtitle API SDK
 */

/**
 * Base error class for all YouTube Subtitle API errors
 */
export class YouTubeSubtitleAPIError extends Error {
  /**
   * @param message - Error message
   * @param code - Optional error code
   * @param status - Optional HTTP status code
   */
  constructor(
    message: string,
    public code?: string,
    public status?: number,
  ) {
    super(message);
    this.name = "YouTubeSubtitleAPIError";
    Object.setPrototypeOf(this, YouTubeSubtitleAPIError.prototype);
  }

  toJSON(): Record<string, unknown> {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      status: this.status,
    };
  }
}

/**
 * Authentication error - invalid or missing API key
 */
export class AuthenticationError extends YouTubeSubtitleAPIError {
  constructor(message: string = "Invalid or missing API key") {
    super(message, "AUTHENTICATION_ERROR", 401);
    this.name = "AuthenticationError";
    Object.setPrototypeOf(this, AuthenticationError.prototype);
  }
}

/**
 * Rate limit error - too many requests
 */
export class RateLimitError extends YouTubeSubtitleAPIError {
  constructor(
    message: string = "Rate limit exceeded. Please retry later.",
    public retryAfter?: number,
  ) {
    super(message, "RATE_LIMIT_ERROR", 429);
    this.name = "RateLimitError";
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }

  toJSON(): Record<string, unknown> {
    return {
      ...super.toJSON(),
      retryAfter: this.retryAfter,
    };
  }
}

/**
 * Not found error - resource not found
 */
export class NotFoundError extends YouTubeSubtitleAPIError {
  constructor(message: string = "Resource not found") {
    super(message, "NOT_FOUND_ERROR", 404);
    this.name = "NotFoundError";
    Object.setPrototypeOf(this, NotFoundError.prototype);
  }
}

/**
 * Validation error - invalid request parameters
 */
export class ValidationError extends YouTubeSubtitleAPIError {
  constructor(
    message: string,
    public field?: string,
  ) {
    super(message, "VALIDATION_ERROR", 400);
    this.name = "ValidationError";
    Object.setPrototypeOf(this, ValidationError.prototype);
  }

  toJSON(): Record<string, unknown> {
    return {
      ...super.toJSON(),
      field: this.field,
    };
  }
}

/**
 * Service unavailable error
 */
export class ServiceUnavailableError extends YouTubeSubtitleAPIError {
  constructor(message: string = "Service unavailable. Please retry later.") {
    super(message, "SERVICE_UNAVAILABLE", 503);
    this.name = "ServiceUnavailableError";
    Object.setPrototypeOf(this, ServiceUnavailableError.prototype);
  }
}

/**
 * Timeout error - request took too long
 */
export class TimeoutError extends YouTubeSubtitleAPIError {
  constructor(message: string = "Request timed out") {
    super(message, "TIMEOUT_ERROR", 408);
    this.name = "TimeoutError";
    Object.setPrototypeOf(this, TimeoutError.prototype);
  }
}

/**
 * Network error - connection issues
 */
export class NetworkError extends YouTubeSubtitleAPIError {
  constructor(message: string = "Network error occurred") {
    super(message, "NETWORK_ERROR");
    this.name = "NetworkError";
    Object.setPrototypeOf(this, NetworkError.prototype);
  }
}

/**
 * Parse an API error response and return the appropriate error class
 *
 * @param response - The fetch Response object
 * @param data - Parsed error response data
 * @returns The appropriate error instance
 */
export function parseAPIError(
  response: Response,
  data?: { detail?: string; code?: string },
): YouTubeSubtitleAPIError {
  const message = data?.detail || response.statusText || "An error occurred";
  const code = data?.code;
  const status = response.status;

  switch (status) {
    case 401:
      return new AuthenticationError(message);
    case 429:
      const retryAfter = response.headers.get("Retry-After");
      return new RateLimitError(
        message,
        retryAfter ? parseInt(retryAfter, 10) : undefined,
      );
    case 404:
      return new NotFoundError(message);
    case 400:
      return new ValidationError(message, code);
    case 503:
      return new ServiceUnavailableError(message);
    case 408:
      return new TimeoutError(message);
    default:
      return new YouTubeSubtitleAPIError(message, code, status);
  }
}

/**
 * Check if an error is a retryable error
 *
 * @param error - The error to check
 * @returns True if the error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  return (
    error instanceof RateLimitError ||
    error instanceof ServiceUnavailableError ||
    error instanceof TimeoutError ||
    error instanceof NetworkError
  );
}
