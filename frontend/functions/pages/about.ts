import { generateHtml } from "./_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title: "About YouTube Subtitle API - Our Mission and Team",
    description:
      "Learn about YouTube Subtitle API. We're making video content accessible by providing tools to extract, download, and work with YouTube subtitles and captions.",
    keywords: [
      "about youtube subtitle api",
      "subtitle extraction service",
      "video accessibility tools",
      "youtube caption tools",
    ],
    heading: "About YouTube Subtitle API",
    subheading: "Making video content accessible and useful",
    content: `YouTube Subtitle API was created to solve a simple problem: extracting subtitles from YouTube videos should be easy, reliable, and free. Whether you're a content creator, developer, researcher, or just someone who needs captions, we provide the tools to get the job done.

Our mission is to make video content more accessible. Subtitles and captions are essential for accessibility, language learning, content repurposing, and SEO. By providing simple tools and a robust API, we help individuals and businesses unlock the value hidden in video captions.`,
    ctaText: "Start Using the API",
    relatedPages: [
      { title: "API Documentation", href: "/docs" },
      { title: "Pricing", href: "/pricing" },
      { title: "YouTube to SRT", href: "/youtube-to-srt" },
    ],
    faqs: [
      {
        question: "Why did you build this service?",
        answer:
          "We needed reliable subtitle extraction for our own projects and couldn't find a free, easy-to-use solution. So we built one. Now we're sharing it with the world.",
      },
      {
        question: "Is this service affiliated with YouTube?",
        answer:
          "No, we're an independent service. We use publicly available YouTube data to extract subtitles that video creators have chosen to make available.",
      },
      {
        question: "How do you ensure service reliability?",
        answer:
          "Our API is built with production-grade infrastructure including Redis caching, PostgreSQL for persistence, RQ workers for background jobs, and comprehensive error handling and monitoring.",
      },
      {
        question: "Can I contribute to the project?",
        answer:
          "Yes! Our codebase is open source. We welcome contributions, bug reports, and feature requests. Check out our GitHub repository to get started.",
      },
      {
        question: "How can I contact support?",
        answer:
          "For technical support, email support@example.com. For sales inquiries, email sales@example.com. We typically respond within 24 hours on business days.",
      },
    ],
  };

  const html = generateHtml(config, origin, path);

  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=UTF-8",
      "Cache-Control": "public, max-age=86400",
    },
  });
};
