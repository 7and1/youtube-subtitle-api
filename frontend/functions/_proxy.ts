/**
 * Cloudflare Pages Functions proxy for backend API.
 *
 * SECURITY: CORS configuration using environment variables.
 * Defaults to denying all origins if ALLOWED_ORIGINS is not configured.
 *
 * Environment variables (set in Cloudflare Pages dashboard):
 * - BACKEND_BASE_URL: The backend API URL (required)
 * - BACKEND_API_KEY: API key for backend authentication (optional)
 * - ALLOWED_ORIGINS: Comma-separated list of allowed origins (required for CORS)
 * - ALLOWED_HEADERS: Comma-separated list of allowed headers (defaults to safe headers)
 *
 * Example ALLOWED_ORIGINS:
 *   https://example.com,https://www.example.com
 *
 * For development, you can use "*" (with quotes) to allow all origins:
 *   ALLOWED_ORIGINS="*"
 */

type BackendEnv = {
  BACKEND_BASE_URL: string;
  BACKEND_API_KEY?: string;
  ALLOWED_ORIGINS?: string;
  ALLOWED_HEADERS?: string;
};

// Safe default headers that don't include wildcard
const DEFAULT_ALLOWED_HEADERS = [
  "Content-Type",
  "Authorization",
  "X-API-Key",
  "X-Requested-With",
];

/**
 * Get allowed origins from environment.
 * Returns empty array if not configured (deny all).
 */
function getAllowedOrigins(env: BackendEnv): string[] {
  const originsStr = env.ALLOWED_ORIGINS?.trim();
  if (!originsStr) {
    // SECURITY: Return empty array to deny all origins by default
    return [];
  }
  if (originsStr === "*") {
    return ["*"];
  }
  return originsStr
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean);
}

/**
 * Get allowed headers from environment or use safe defaults.
 */
function getAllowedHeaders(env: BackendEnv): string[] {
  const headersStr = env.ALLOWED_HEADERS?.trim();
  if (!headersStr) {
    return DEFAULT_ALLOWED_HEADERS;
  }
  if (headersStr === "*") {
    return ["*"];
  }
  return headersStr
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean);
}

/**
 * Check if the given origin is allowed.
 */
function isOriginAllowed(
  origin: string | null,
  allowedOrigins: string[],
): boolean {
  if (!origin) {
    return false;
  }
  if (allowedOrigins.includes("*")) {
    return true;
  }
  return allowedOrigins.some((allowed) => {
    // Support exact match and wildcard subdomain matching
    if (allowed === origin) {
      return true;
    }
    if (allowed.startsWith("*.")) {
      const domain = allowed.slice(2); // Remove *.
      // Match subdomains
      if (origin === domain || origin.endsWith(`.${domain}`)) {
        return true;
      }
    }
    return false;
  });
}

/**
 * Generate CORS headers for the given origin.
 * Returns null if the origin is not allowed.
 */
function corsHeaders(
  origin: string | null,
  env: BackendEnv,
): HeadersInit | null {
  const allowedOrigins = getAllowedOrigins(env);
  const allowedHeaders = getAllowedHeaders(env);

  // If origin is not specified (e.g., same-origin request), return minimal headers
  if (!origin) {
    return {
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Max-Age": "86400",
    };
  }

  // Check if origin is allowed
  if (!isOriginAllowed(origin, allowedOrigins)) {
    // Origin not allowed - return null to signal no CORS headers
    return null;
  }

  // Determine the value for Access-Control-Allow-Origin
  const allowOriginValue = allowedOrigins.includes("*") ? "*" : origin;

  return {
    "Access-Control-Allow-Origin": allowOriginValue,
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": allowedHeaders.join(", "),
    "Access-Control-Allow-Credentials": allowedOrigins.includes("*")
      ? "false"
      : "true",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

export function requireBackendBase(env: BackendEnv): string {
  const backendBase = (env.BACKEND_BASE_URL || "").replace(/\/$/, "");
  if (!backendBase) throw new Error("Missing BACKEND_BASE_URL");
  return backendBase;
}

export function optionsResponse(request: Request, env: BackendEnv): Response {
  const origin = request.headers.get("Origin");
  const headers = corsHeaders(origin, env);

  if (!headers) {
    // Origin not allowed
    return new Response(null, { status: 204 });
  }

  return new Response(null, { status: 204, headers });
}

export async function proxyToBackend(
  request: Request,
  env: BackendEnv,
  url: string,
): Promise<Response> {
  const origin = request.headers.get("Origin");
  const cors = corsHeaders(origin, env);

  // Handle preflight request
  if (request.method === "OPTIONS") {
    return optionsResponse(request, env);
  }

  const headers = new Headers(request.headers);
  headers.delete("host");
  if (env.BACKEND_API_KEY) headers.set("X-API-Key", env.BACKEND_API_KEY);

  const init: RequestInit = {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method.toUpperCase())
      ? undefined
      : await request.arrayBuffer(),
    redirect: "manual",
  };

  const resp = await fetch(url, init);
  const outHeaders = new Headers(resp.headers);

  // Only add CORS headers if origin is allowed
  if (cors) {
    for (const [k, v] of Object.entries(cors)) {
      outHeaders.set(k, v);
    }
  }

  return new Response(resp.body, { status: resp.status, headers: outHeaders });
}
