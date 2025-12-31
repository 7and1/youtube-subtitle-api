import { generateHtml } from "./_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title: "YouTube to SRT Converter - Download YouTube Subtitles as SRT Files",
    description:
      "Free online tool to download YouTube subtitles as SRT (SubRip) files. Extract captions from any YouTube video in SRT format. Compatible with VLC, Media Player, and video editing software.",
    keywords: [
      "youtube to srt",
      "youtube subtitle download srt",
      "extract youtube subtitles srt",
      "youtube caption converter",
      "download youtube subtitles",
      "srt converter",
      "subtitle extractor",
    ],
    heading: "YouTube to SRT Converter",
    subheading: "Download YouTube subtitles as SRT (SubRip) format files",
    content: `Convert and download YouTube subtitles as SRT files. The SRT (SubRip) format is the most widely supported subtitle format, compatible with virtually all video players including VLC, Windows Media Player, MPC-HC, and video editing software like Adobe Premiere and DaVinci Resolve.

Our tool extracts both manual subtitles and auto-generated captions from YouTube videos, converting them to properly formatted SRT files with accurate timing information. Simply paste the YouTube URL or video ID, select your preferred language, and get your SRT file instantly.`,
    ctaText: "Convert to SRT Now",
    relatedPages: [
      { title: "YouTube to VTT", href: "/youtube-to-vtt" },
      { title: "YouTube to TXT", href: "/youtube-to-txt" },
      {
        title: "YouTube English Subtitles",
        href: "/youtube-english-subtitles",
      },
      {
        title: "Subtitle Downloader Tool",
        href: "/tools/youtube-subtitle-downloader",
      },
    ],
    faqs: [
      {
        question: "What is an SRT file?",
        answer:
          "SRT (SubRip Text) is a standard subtitle file format that contains timed text captions with sequence numbers, timestamps, and subtitle text. It's the most compatible format for video players and editing software.",
      },
      {
        question: "How do I use SRT files with videos?",
        answer:
          "Most video players like VLC, MPC-HC, and PotPlayer automatically load SRT files if they have the same filename as your video. You can also manually load subtitles through the player's subtitle menu.",
      },
      {
        question: "Can I edit the downloaded SRT files?",
        answer:
          "Yes! SRT files are plain text files that can be edited with any text editor. You can adjust timing, correct text, or translate the content using tools likeSubtitle Edit or Aegisub.",
      },
      {
        question: "Do SRT files support special characters and formatting?",
        answer:
          "Yes, SRT files support Unicode characters, so they work with all languages. Basic formatting like italic and bold text is also supported by most players.",
      },
      {
        question: "Why choose SRT over other formats?",
        answer:
          "SRT is the most universal subtitle format. If you're unsure which format to choose, SRT is compatible with the widest range of software and hardware players.",
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
