import { generateHtml } from "../pages/_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title:
      "YouTube Subtitle Downloader - Free Online Tool to Download YouTube Subtitles",
    description:
      "Free YouTube subtitle downloader tool. Download subtitles from any YouTube video in SRT, VTT, or TXT format. No registration required. Works with all languages.",
    keywords: [
      "youtube subtitle downloader",
      "youtube caption downloader",
      "download youtube subtitles",
      "subtitle extractor",
      "free subtitle downloader",
      "youtube to srt downloader",
      "caption download tool",
    ],
    heading: "YouTube Subtitle Downloader",
    subheading: "Download subtitles from any YouTube video in seconds",
    content: `Our YouTube subtitle downloader lets you extract and download subtitles from any YouTube video quickly and easily. Whether you need subtitles for translation, accessibility, content creation, or language learning, our tool provides high-quality subtitle files in multiple formats.

Simply paste the YouTube video URL or ID, select your preferred language and output format (SRT for video players, VTT for web, or TXT for plain text), and download your subtitle file instantly. Our tool works with both manually uploaded subtitles and YouTube's auto-generated captions.`,
    ctaText: "Download Subtitles Now",
    relatedPages: [
      { title: "YouTube to SRT", href: "/youtube-to-srt" },
      { title: "YouTube to VTT", href: "/youtube-to-vtt" },
      { title: "YouTube to TXT", href: "/youtube-to-txt" },
      { title: "English Subtitles", href: "/youtube-english-subtitles" },
      { title: "Batch Downloader", href: "/tools/batch-downloader" },
    ],
    faqs: [
      {
        question: "How do I download subtitles from a YouTube video?",
        answer:
          "Paste the YouTube video URL into the input field above, select your preferred language and output format (SRT, VTT, or TXT), then click the download button. Your subtitle file will be generated instantly.",
      },
      {
        question: "Can I download subtitles from any YouTube video?",
        answer:
          "You can download subtitles from any public YouTube video that has subtitles available. This includes both manually uploaded subtitles and auto-generated captions.",
      },
      {
        question: "What subtitle formats are supported?",
        answer:
          "We support three main formats: SRT (SubRip) for video players and editing software, VTT (WebVTT) for HTML5 web players, and TXT for plain text transcripts.",
      },
      {
        question: "Are downloaded subtitles accurate?",
        answer:
          "Manually uploaded subtitles are typically very accurate as they're created by the video creator. Auto-generated subtitles use YouTube's speech recognition and are generally good but may have occasional errors.",
      },
      {
        question: "Do I need to register or pay to download subtitles?",
        answer:
          "No! Our YouTube subtitle downloader is completely free and requires no registration. Just paste the URL and download.",
      },
      {
        question: "Can I download subtitles in different languages?",
        answer:
          "Yes! If the YouTube video has subtitles available in multiple languages, you can select and download any of them. We support all 100+ languages available on YouTube.",
      },
      {
        question: "What can I do with downloaded subtitles?",
        answer:
          "Use them with video players, add subtitles to your own videos, translate content, create transcripts for SEO, use for language learning, or generate content summaries.",
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
