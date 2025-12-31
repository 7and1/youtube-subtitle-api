import { generateHtml } from "../pages/_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title:
      "Batch YouTube Subtitle Downloader - Download Multiple YouTube Subtitles at Once",
    description:
      "Batch download subtitles from multiple YouTube videos. Extract subtitles from entire playlists or multiple videos in SRT, VTT, or TXT format. Save time with bulk subtitle extraction.",
    keywords: [
      "batch youtube subtitle downloader",
      "bulk subtitle download",
      "playlist subtitle downloader",
      "multiple youtube subtitles",
      "mass subtitle extractor",
      "youtube playlist subtitles",
      "bulk caption download",
    ],
    heading: "Batch YouTube Subtitle Downloader",
    subheading: "Download subtitles from multiple YouTube videos at once",
    content: `Our batch subtitle downloader lets you extract subtitles from multiple YouTube videos simultaneously. Perfect for content creators, researchers, and businesses who need to process large numbers of videos.

Simply provide a list of YouTube video URLs or a playlist URL, select your preferred language and format, and our system will extract all available subtitles. The batch downloader is ideal for creating training datasets, content analysis, translation workflows, and archival projects.`,
    ctaText: "Start Batch Download",
    relatedPages: [
      {
        title: "Single Video Downloader",
        href: "/tools/youtube-subtitle-downloader",
      },
      { title: "YouTube to SRT", href: "/youtube-to-srt" },
      { title: "YouTube to VTT", href: "/youtube-to-vtt" },
      { title: "API Documentation", href: "/docs" },
    ],
    faqs: [
      {
        question: "How does batch subtitle downloading work?",
        answer:
          "Provide multiple YouTube URLs or a playlist link, select your language and format preferences, then start the batch process. Our system will process each video and provide downloadable files or a ZIP archive of all subtitles.",
      },
      {
        question: "Is there a limit on how many videos I can process?",
        answer:
          "Free tier allows processing up to 50 videos per batch. API users can process larger batches by implementing their own queuing system using our API endpoints.",
      },
      {
        question: "Can I download subtitles from entire playlists?",
        answer:
          "Yes! Simply paste the playlist URL and our tool will extract subtitles from all videos in the playlist that have available captions.",
      },
      {
        question: "What formats are supported for batch downloads?",
        answer:
          "You can choose SRT, VTT, or TXT format for your batch download. All files in the batch will use the same format for consistency.",
      },
      {
        question: "How long does batch processing take?",
        answer:
          "Processing time depends on the number of videos and whether captions are cached. Cached results return instantly, while new extractions typically take 10-30 seconds per video.",
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
