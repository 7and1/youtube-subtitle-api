import { generateHtml } from "./_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title: "YouTube to TXT - Extract YouTube Video Transcripts as Plain Text",
    description:
      "Free tool to extract and download YouTube video transcripts as plain text files. Perfect for content analysis, AI training data, documentation, and reading video content offline.",
    keywords: [
      "youtube to txt",
      "youtube transcript download",
      "extract youtube transcript",
      "youtube video to text",
      "youtube caption text",
      "youtube subtitle text",
      "video transcript extractor",
    ],
    heading: "YouTube to TXT Transcript Extractor",
    subheading: "Download YouTube video transcripts as plain text files",
    content: `Extract the full transcript of any YouTube video as clean, readable plain text. This tool removes all timestamps and formatting, giving you just the spoken content in a simple TXT file that's perfect for reading, analyzing, or repurposing content.

Plain text transcripts are invaluable for content creators, researchers, students, and businesses. Use them to create blog posts, summaries, training materials, or as input for AI and machine learning projects. Our tool preserves paragraph breaks and removes all subtitle formatting for maximum readability.`,
    ctaText: "Extract Transcript Now",
    relatedPages: [
      { title: "YouTube to SRT", href: "/youtube-to-srt" },
      { title: "YouTube to VTT", href: "/youtube-to-vtt" },
      {
        title: "YouTube English Subtitles",
        href: "/youtube-english-subtitles",
      },
    ],
    faqs: [
      {
        question: "What's the difference between a transcript and subtitles?",
        answer:
          "A transcript is a plain text version of the spoken content without timestamps or formatting. Subtitles (like SRT or VTT) include timing information for synchronizing with video playback.",
      },
      {
        question: "Can I use transcripts for content creation?",
        answer:
          "Absolutely! Plain text transcripts are perfect for creating blog posts, articles, social media content, summaries, and repurposing video content into other formats.",
      },
      {
        question: "Are transcripts useful for SEO?",
        answer:
          "Yes! Search engines can index text content much better than video. Adding transcripts to your website can significantly improve SEO and help users find your content through search.",
      },
      {
        question: "Can I use transcripts for AI training data?",
        answer:
          "Plain text transcripts are excellent for training AI models, fine-tuning language models, or as input for content analysis tools. The clean text format is ideal for machine learning pipelines.",
      },
      {
        question: "How do you handle multiple speakers in transcripts?",
        answer:
          "Our plain text format preserves the flow of conversation. For speaker identification, consider using the SRT format which may include speaker labels in the subtitle text.",
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
