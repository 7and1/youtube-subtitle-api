import { generateHtml } from "./_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title:
      "YouTube Subtitle API Documentation - REST API for Subtitle Extraction",
    description:
      "Complete API documentation for the YouTube Subtitle API. Learn how to extract YouTube subtitles programmatically with our REST API. Includes code examples and integration guides.",
    keywords: [
      "youtube subtitle api",
      "subtitle extraction api",
      "youtube captions api",
      "rest api documentation",
      "subtitle api integration",
      "youtube transcript api",
      "programmatic subtitle download",
    ],
    heading: "YouTube Subtitle API Documentation",
    subheading: "Integrate subtitle extraction into your applications",
    content: `Our YouTube Subtitle API provides a simple, powerful REST interface for extracting subtitles from YouTube videos. Built with FastAPI and backed by production-grade infrastructure, the API supports async processing, intelligent caching, rate limiting, and comprehensive metrics.

The API is designed for developers who need to integrate subtitle extraction into their applications, whether for content analysis, accessibility tools, translation services, or automated workflows.`,
    ctaText: "View API Reference",
    relatedPages: [
      { title: "Pricing", href: "/pricing" },
      { title: "About", href: "/about" },
      { title: "YouTube to SRT", href: "/youtube-to-srt" },
      { title: "Tools", href: "/tools/youtube-subtitle-downloader" },
    ],
    faqs: [
      {
        question: "How do I authenticate with the API?",
        answer:
          "API requests require an X-API-Key header. Sign up for a free API key in your dashboard. The free tier includes 1,000 requests per day.",
      },
      {
        question: "What are the API endpoints?",
        answer:
          "Main endpoints include: POST /api/subtitles to extract subtitles, GET /api/subtitles/{video_id} to retrieve cached results, and GET /api/job/{job_id} to check async job status.",
      },
      {
        question: "How does async processing work?",
        answer:
          "For new video extractions, the API returns a 202 status with a job_id. Poll the /api/job/{job_id} endpoint until status is 'completed'. Cached results return immediately with 200 status.",
      },
      {
        question: "What formats does the API return?",
        answer:
          "The API returns JSON by default with raw subtitle data. You can specify format parameters to get SRT, VTT, or plain text output directly.",
      },
      {
        question: "Are there rate limits?",
        answer:
          "Yes, rate limits depend on your plan. Free tier: 1,000 requests/day. Pro tier: 10,000 requests/day. Enterprise: custom limits. Responses include rate limit headers.",
      },
      {
        question: "Can I use the API with YouTube's auto-generated captions?",
        answer:
          "Yes! The API extracts both manual and auto-generated captions. Use the 'auto_caption=true' parameter to prefer auto-generated subtitles when manual ones aren't available.",
      },
    ],
  };

  const html = generateHtml(config, origin, path);

  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=UTF-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};
