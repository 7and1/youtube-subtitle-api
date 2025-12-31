import "./styles.css";

type ApiResponse = { status: number; json: unknown; retryAfter?: number };

const STORAGE_KEY_API_BASE = "yt-subtitles:apiBase";

// YouTube URL patterns for validation
const YOUTUBE_PATTERNS = [
  /^https?:\/\/(www\.)?youtube\.com\/watch\?v=[a-zA-Z0-9_-]{11}/,
  /^https?:\/\/youtu\.be\/[a-zA-Z0-9_-]{11}/,
  /^https?:\/\/(www\.)?youtube\.com\/embed\/[a-zA-Z0-9_-]{11}/,
  /^https?:\/\/(www\.)?youtube\.com\/v\/[a-zA-Z0-9_-]{11}/,
  /^[a-zA-Z0-9_-]{11}$/, // Just the video ID
];

function classifyStatus(status: string) {
  const s = String(status || "idle").toLowerCase();
  if (["finished", "success", "ok"].includes(s))
    return { text: s, cls: "good" };
  if (
    [
      "queued",
      "started",
      "deferred",
      "scheduled",
      "running",
      "requesting",
    ].includes(s)
  )
    return { text: s, cls: "warn" };
  if (["failed", "error", "timeout"].includes(s))
    return { text: s, cls: "bad" };
  return { text: s, cls: "" };
}

function getErrorType(
  status: number,
  json: unknown,
): { title: string; message: string; canRetry: boolean } {
  if (status === 429) {
    const retryAfter = (json as any)?.retry_after;
    return {
      title: "Rate limit exceeded",
      message: retryAfter
        ? `Too many requests. Please wait ${retryAfter} seconds before trying again.`
        : "Too many requests. Please wait before trying again.",
      canRetry: true,
    };
  }
  if (status === 404) {
    return {
      title: "Video not found",
      message:
        "No subtitles found for this video. The video may not exist or may not have captions available.",
      canRetry: false,
    };
  }
  if (status === 400) {
    return {
      title: "Invalid request",
      message:
        (json as any)?.detail || "Please check your input and try again.",
      canRetry: false,
    };
  }
  if (status >= 500) {
    return {
      title: "Server error",
      message: "The server encountered an error. Please try again later.",
      canRetry: true,
    };
  }
  if (status === 0 || status >= 600) {
    return {
      title: "Network error",
      message:
        "Unable to connect to the server. Please check your connection and try again.",
      canRetry: true,
    };
  }
  return {
    title: "Request failed",
    message: (json as any)?.detail || "An unexpected error occurred.",
    canRetry: true,
  };
}

function normalizeVideoInput(input: string) {
  const v = input.trim();
  if (!v)
    return { video_id: null as string | null, url: null as string | null };
  if (/^[a-zA-Z0-9_-]{11}$/.test(v)) return { video_id: v, url: null };
  return { video_id: null, url: v };
}

function validateYouTubeUrl(input: string): {
  valid: boolean;
  message: string;
} {
  const trimmed = input.trim();
  if (!trimmed) {
    return { valid: false, message: "" };
  }
  if (YOUTUBE_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return { valid: true, message: "" };
  }
  return {
    valid: false,
    message: "Please enter a valid YouTube URL or 11-character video ID",
  };
}

function getEnvApiBase(): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const env = (import.meta as any).env as Record<string, string | undefined>;
  return (env?.VITE_API_BASE_URL || "").replace(/\/$/, "");
}

function getApiBase(): string {
  const stored = (localStorage.getItem(STORAGE_KEY_API_BASE) || "").trim();
  return (stored || getEnvApiBase() || "").replace(/\/$/, "");
}

function setApiBase(value: string) {
  const v = value.trim().replace(/\/$/, "");
  if (!v) localStorage.removeItem(STORAGE_KEY_API_BASE);
  else localStorage.setItem(STORAGE_KEY_API_BASE, v);
}

async function apiFetch(path: string, body?: unknown): Promise<ApiResponse> {
  const base = getApiBase();
  const url = base ? `${base}${path}` : path;
  const res = await fetch(url, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }

  // Extract retry-after header for rate limiting
  const retryAfter = res.headers.get("Retry-After");
  const retryAfterNum = retryAfter ? parseInt(retryAfter, 10) : undefined;

  return { status: res.status, json, retryAfter: retryAfterNum };
}

async function pollJob(
  jobId: string,
  onUpdate: (s: unknown) => void,
  onError: (error: ApiResponse) => void,
) {
  const deadline = Date.now() + 90_000;
  let attempts = 0;
  const maxAttempts = 90;

  while (Date.now() < deadline && attempts < maxAttempts) {
    attempts++;
    const { status, json } = await apiFetch(
      `/api/job/${encodeURIComponent(jobId)}`,
    );
    if (status !== 200) {
      onError({ status, json });
      return;
    }
    onUpdate(json);
    const j = json as any;
    if (j?.status === "finished" || j?.status === "failed") return;
    await new Promise((r) => setTimeout(r, 1000));
  }
  onUpdate({ status: "timeout" });
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
      document.body.removeChild(textarea);
      return true;
    } catch {
      document.body.removeChild(textarea);
      return false;
    }
  }
}

// Toast notification system
function showToast(
  message: string,
  type: "success" | "error" | "info" = "info",
  duration = 3000,
) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Button copy feedback
function setCopyFeedback(button: HTMLButtonElement, success: boolean) {
  const copyText = button.querySelector(".copy-text");
  const copyCheck = button.querySelector(".copy-check");

  if (copyText && copyCheck) {
    if (success) {
      copyText.hidden = true;
      copyCheck.hidden = false;
      setTimeout(() => {
        copyText.hidden = false;
        copyCheck.hidden = true;
      }, 2000);
    } else {
      // Shake animation for error
      button.classList.add("shake");
      setTimeout(() => button.classList.remove("shake"), 500);
    }
  }
}

// Format conversion functions
function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(ms).padStart(3, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(ms).padStart(3, "0")}`;
}

function convertToSRT(json: unknown): string {
  const data = json as any;
  if (!data?.subtitles || !Array.isArray(data.subtitles)) {
    // Fallback to plain text
    return data?.plain_text || "No subtitles available";
  }

  return data.subtitles
    .map((sub: any, index: number) => {
      const start = formatTimestamp(sub.start || 0);
      const end = formatTimestamp(sub.end || sub.start || 0);
      return `${index + 1}\n${start} --> ${end}\n${sub.text || ""}\n`;
    })
    .join("\n");
}

function convertToVTT(json: unknown): string {
  const data = json as any;
  if (!data?.subtitles || !Array.isArray(data.subtitles)) {
    return `WEBVTT\n\n${data?.plain_text || "No subtitles available"}`;
  }

  let vtt = "WEBVTT\n\n";
  vtt += data.subtitles
    .map((sub: any) => {
      const start = formatTimestamp(sub.start || 0).replace(",", ".");
      const end = formatTimestamp(sub.end || sub.start || 0).replace(",", ".");
      return `${start} --> ${end}\n${sub.text || ""}`;
    })
    .join("\n\n");

  return vtt;
}

function convertToTXT(json: unknown): string {
  const data = json as any;
  return data?.plain_text || "No text available";
}

// Download handlers
function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const qs = <T extends HTMLElement>(id: string) => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing #${id}`);
  return el as T;
};

const yearEl = qs<HTMLSpanElement>("year");
yearEl.textContent = String(new Date().getFullYear());

const statusEl = qs<HTMLDivElement>("status");
const metaEl = qs<HTMLDivElement>("meta");
const outputEl = qs<HTMLTextAreaElement>("output");
const rawEl = qs<HTMLPreElement>("raw");
const rawCodeEl = rawEl.querySelector("code") || rawEl;
const docsLink = qs<HTMLAnchorElement>("link-docs");
const healthLink = qs<HTMLAnchorElement>("link-health");
const metricsLink = qs<HTMLAnchorElement>("link-metrics");
const curlEl = qs<HTMLElement>("curl");

const form = qs<HTMLFormElement>("form");
const videoInput = qs<HTMLInputElement>("video");
const videoIcon = qs<HTMLDivElement>("video-icon");
const videoHint = qs<HTMLSpanElement>("video-hint");
const langInput = qs<HTMLInputElement>("lang");
const cleanInput = qs<HTMLInputElement>("clean");
const baseInput = qs<HTMLInputElement>("base");

const fillDemoBtn = qs<HTMLButtonElement>("fill-demo");
const copyCurlBtn = qs<HTMLButtonElement>("copy-curl");
const copyTextBtn = qs<HTMLButtonElement>("copy-text");
const copyJsonBtn = qs<HTMLButtonElement>("copy-json");
const retryBtn = qs<HTMLButtonElement>("retry-btn");
const downloadDropdown = qs<HTMLDivElement>("download-dropdown");
const submitBtn = qs<HTMLButtonElement>("submit");

// Skeleton and error states
const skeletonEl = qs<HTMLDivElement>("skeleton");
const errorStateEl = qs<HTMLDivElement>("error-state");
const errorTitleEl = qs<HTMLDivElement>("error-title");
const errorMessageEl = qs<HTMLDivElement>("error-message");
const resultActionsEl = qs<HTMLDivElement>("result-actions");

// Mobile menu
const mobileMenuBtn = qs<HTMLButtonElement>("mobile-menu-btn");
const navEl = qs<HTMLElement>("nav");

// Rate limit banner
const rateLimitBanner = qs<HTMLDivElement>("rate-limit-banner");
const rateLimitDesc = qs<HTMLDivElement>("rate-limit-desc");

// Current state
let currentResult: unknown = null;
let lastFormData: {
  video: string;
  language: string;
  clean_for_ai: boolean;
} | null = null;

function syncBackendLinks() {
  const base = getApiBase();
  docsLink.href = base ? `${base}/docs` : "/docs";
  healthLink.href = base ? `${base}/health` : "/health";
  metricsLink.href = base ? `${base}/metrics` : "/metrics";
  for (const el of [docsLink, healthLink, metricsLink])
    el.title = base ? "Direct backend link" : "Proxied via Pages/Vite";
}

function setStatus(status: string) {
  const { text, cls } = classifyStatus(status);
  statusEl.textContent = text;
  statusEl.className = "pill" + (cls ? ` ${cls}` : "");
}

function setLoading(loading: boolean) {
  submitBtn.disabled = loading;
  submitBtn.classList.toggle("loading", loading);

  // Toggle skeleton visibility
  if (loading) {
    skeletonEl.hidden = false;
    errorStateEl.hidden = true;
    outputEl.hidden = true;
    resultActionsEl.hidden = true;
  } else {
    skeletonEl.hidden = true;
  }
}

function showError(title: string, message: string, canRetry = false) {
  errorTitleEl.textContent = title;
  errorMessageEl.textContent = message;
  errorStateEl.hidden = false;
  outputEl.hidden = true;
  resultActionsEl.hidden = !canRetry;
  retryBtn.hidden = !canRetry;
  skeletonEl.hidden = true;

  showToast(title, "error");
}

function hideError() {
  errorStateEl.hidden = true;
  retryBtn.hidden = true;
}

function showResult() {
  errorStateEl.hidden = true;
  skeletonEl.hidden = true;
  outputEl.hidden = false;
  resultActionsEl.hidden = false;
}

function renderCurl() {
  const base = getApiBase();
  const url = base ? `${base}/api/subtitles` : "/api/subtitles";
  const language = (langInput.value.trim() || "en").replace(/"/g, "");
  const clean_for_ai = cleanInput.checked;
  curlEl.textContent = `curl -X POST ${url} \\\n  -H "Content-Type: application/json" \\\n  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"${language}","clean_for_ai":${clean_for_ai}}'`;
}

// JSON syntax highlighting
function syntaxHighlight(json: string): string {
  return json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = "json-number";
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = "json-key";
          } else {
            cls = "json-string";
          }
        } else if (/true|false/.test(match)) {
          cls = "json-boolean";
        } else if (/null/.test(match)) {
          cls = "json-null";
        }
        return `<span class="${cls}">${match}</span>`;
      },
    );
}

function setResultJson(json: unknown) {
  currentResult = json;
  const jsonString = JSON.stringify(json, null, 2);
  rawCodeEl.innerHTML = syntaxHighlight(jsonString);

  const j = json as any;
  const title = j?.title ? `Title: ${j.title}` : "";
  const meta = [
    j?.video_id ? `Video: ${j.video_id}` : "",
    j?.language ? `Language: ${j.language}` : "",
    j?.extraction_method ? `Method: ${j.extraction_method}` : "",
    j?.cached !== undefined ? `Cached: ${j.cached}` : "",
    j?.duration_ms ? `Duration: ${j.duration_ms}ms` : "",
    j?.proxy_used ? `Proxy: ${j.proxy_used}` : "",
  ]
    .filter(Boolean)
    .join(" • ");

  metaEl.textContent = [title, meta]
    .filter(Boolean)
    .join(title && meta ? "\n" : "");
  outputEl.value = j?.plain_text || "";
}

// Input validation
function validateVideoInput() {
  const value = videoInput.value;
  const result = validateYouTubeUrl(value);

  if (value && !result.valid) {
    videoIcon.textContent = "!";
    videoIcon.classList.add("invalid");
    videoInput.classList.add("input-invalid");
    videoHint.textContent = result.message;
    videoHint.classList.add("hint-error");
  } else if (value && result.valid) {
    videoIcon.textContent = "✓";
    videoIcon.classList.remove("invalid");
    videoIcon.classList.add("valid");
    videoInput.classList.remove("input-invalid");
    videoInput.classList.add("input-valid");
    videoHint.textContent = "";
    videoHint.classList.remove("hint-error");
  } else {
    videoIcon.textContent = "";
    videoIcon.classList.remove("invalid", "valid");
    videoInput.classList.remove("input-invalid", "input-valid");
    videoHint.textContent = "";
    videoHint.classList.remove("hint-error");
  }
}

baseInput.value = getApiBase();
syncBackendLinks();
renderCurl();

// Mobile menu toggle
mobileMenuBtn.addEventListener("click", () => {
  navEl.classList.toggle("nav-open");
  mobileMenuBtn.classList.toggle("menu-open");
});

for (const el of [langInput, cleanInput, baseInput]) {
  el.addEventListener("change", () => {
    if (el === baseInput) setApiBase(baseInput.value);
    syncBackendLinks();
    renderCurl();
  });
  el.addEventListener("input", () => {
    if (el === baseInput) setApiBase(baseInput.value);
    syncBackendLinks();
    renderCurl();
  });
}

// Video input validation
videoInput.addEventListener("input", validateVideoInput);
videoInput.addEventListener("blur", validateVideoInput);

fillDemoBtn.addEventListener("click", () => {
  videoInput.value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
  langInput.value = "en";
  cleanInput.checked = true;
  videoInput.focus();
  validateVideoInput();
  renderCurl();
});

copyCurlBtn.addEventListener("click", async () => {
  const success = await copyToClipboard(String(curlEl.textContent || ""));
  setCopyFeedback(copyCurlBtn, success);
  if (success) showToast("curl command copied!", "success");
});

copyTextBtn.addEventListener("click", async () => {
  if (!outputEl.value) {
    showToast("No text to copy", "error");
    return;
  }
  const success = await copyToClipboard(outputEl.value);
  setCopyFeedback(copyTextBtn, success);
  if (success) showToast("Text copied to clipboard", "success");
});

copyJsonBtn.addEventListener("click", async () => {
  const text = rawCodeEl.textContent || "";
  if (!text) {
    showToast("No JSON to copy", "error");
    return;
  }
  const success = await copyToClipboard(text);
  setCopyFeedback(copyJsonBtn, success);
  if (success) showToast("JSON copied to clipboard", "success");
});

// Download dropdown handling
downloadDropdown.addEventListener("click", (e) => {
  const toggle = downloadDropdown.querySelector(".dropdown-toggle");
  const menu = downloadDropdown.querySelector(".dropdown-menu");

  if (e.target === toggle || toggle?.contains(e.target as Node)) {
    e.stopPropagation();
    menu?.classList.toggle("show");
  }
});

// Close dropdown when clicking outside
document.addEventListener("click", () => {
  const menu = downloadDropdown.querySelector(".dropdown-menu");
  menu?.classList.remove("show");
});

// Download format handlers
downloadDropdown.querySelectorAll(".dropdown-item").forEach((item) => {
  item.addEventListener("click", (e) => {
    e.stopPropagation();
    const format = (item as HTMLButtonElement).dataset.format;
    if (!format || !currentResult) return;

    const videoId = (currentResult as any)?.video_id || "subtitles";
    const timestamp = new Date().toISOString().slice(0, 10);

    switch (format) {
      case "json":
        downloadFile(
          JSON.stringify(currentResult, null, 2),
          `${videoId}_${timestamp}.json`,
          "application/json",
        );
        showToast("Downloaded as JSON", "success");
        break;
      case "srt":
        downloadFile(
          convertToSRT(currentResult),
          `${videoId}_${timestamp}.srt`,
          "text/plain",
        );
        showToast("Downloaded as SRT", "success");
        break;
      case "vtt":
        downloadFile(
          convertToVTT(currentResult),
          `${videoId}_${timestamp}.vtt`,
          "text/plain",
        );
        showToast("Downloaded as VTT", "success");
        break;
      case "txt":
        downloadFile(
          convertToTXT(currentResult),
          `${videoId}_${timestamp}.txt`,
          "text/plain",
        );
        showToast("Downloaded as TXT", "success");
        break;
    }
  });
});

// Retry button
retryBtn.addEventListener("click", () => {
  if (lastFormData) {
    form.dispatchEvent(new Event("submit"));
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Validate input
  const validation = validateYouTubeUrl(videoInput.value);
  if (!validation.valid && videoInput.value) {
    showError("Invalid input", validation.message, false);
    return;
  }

  outputEl.value = "";
  rawCodeEl.innerHTML = "";
  metaEl.textContent = "";
  hideError();

  const videoRaw = videoInput.value;
  const language = langInput.value.trim() || "en";
  const clean_for_ai = cleanInput.checked;

  // Store for retry
  lastFormData = { video: videoRaw, language, clean_for_ai };

  setStatus("requesting");
  setLoading(true);

  const payload: any = { language, clean_for_ai };
  Object.assign(payload, normalizeVideoInput(videoRaw));

  try {
    const { status, json, retryAfter } = await apiFetch(
      "/api/subtitles",
      payload,
    );

    // Handle rate limiting
    if (status === 429) {
      const error = getErrorType(status, json);
      setLoading(false);
      setStatus("failed");
      showError(error.title, error.message, error.canRetry);

      // Show rate limit banner
      if (retryAfter) {
        rateLimitDesc.textContent = `Too many requests. Please wait ${retryAfter} seconds before trying again.`;
      } else {
        rateLimitDesc.textContent = error.message;
      }
      rateLimitBanner.hidden = false;
      return;
    } else {
      rateLimitBanner.hidden = true;
    }

    if (status === 200) {
      setLoading(false);
      setStatus("finished");
      showResult();
      setResultJson(json);
      showToast("Subtitles extracted successfully!", "success");
      return;
    }

    if (status === 202 && (json as any)?.job_id) {
      setStatus("queued");
      await pollJob(
        String((json as any).job_id),
        (state) => {
          const s = (state as any)?.status || "queued";
          setStatus(String(s));
          if (s === "finished" && (state as any)?.result) {
            setLoading(false);
            showResult();
            setResultJson((state as any).result);
            showToast("Subtitles extracted successfully!", "success");
          } else if (s === "failed") {
            setLoading(false);
            const error = getErrorType(500, state);
            showError(error.title, error.message, error.canRetry);
          } else {
            setResultJson(state);
          }
        },
        (error) => {
          setLoading(false);
          const err = getErrorType(error.status, error.json);
          setStatus("failed");
          showError(err.title, err.message, err.canRetry);
        },
      );
      return;
    }

    // Handle other errors
    const error = getErrorType(status, json);
    setLoading(false);
    setStatus("failed");
    showError(error.title, error.message, error.canRetry);
  } catch (err) {
    const error = getErrorType(0, { detail: "Network error" });
    setLoading(false);
    setStatus("failed");
    showError(error.title, error.message, error.canRetry);
  }
});

// Handle FAQ items for better accordion behavior
document.querySelectorAll(".faq-item").forEach((item) => {
  const summary = item.querySelector("summary");
  if (!summary) return;

  summary.addEventListener("click", (e) => {
    // Close other FAQ items
    document.querySelectorAll(".faq-item").forEach((other) => {
      if (other !== item && other.hasAttribute("open")) {
        other.removeAttribute("open");
      }
    });
  });
});

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
  // Ctrl/Cmd + Enter to submit
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !submitBtn.disabled) {
    form.dispatchEvent(new Event("submit"));
  }
  // Escape to close dropdown
  if (e.key === "Escape") {
    const menu = downloadDropdown.querySelector(".dropdown-menu");
    menu?.classList.remove("show");
  }
});
