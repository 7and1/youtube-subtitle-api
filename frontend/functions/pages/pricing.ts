import { generateHtml } from "./_template";
import type { PagesFunction } from "@cloudflare/workers-types";

export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  const config = {
    title: "YouTube Subtitle API Pricing - Free and Paid Plans",
    description:
      "Simple, transparent pricing for the YouTube Subtitle API. Free tier for personal projects, Pro for businesses, and Enterprise for high-volume needs.",
    keywords: [
      "youtube subtitle api pricing",
      "subtitle api free",
      "youtube transcription cost",
      "api pricing plans",
      "bulk subtitle pricing",
      "youtube api cost",
    ],
    heading: "Simple, Transparent Pricing",
    subheading: "Start free, scale as you grow",
    content: `Our pricing is designed to be simple and predictable. Whether you're a hobbyist working on personal projects or a business processing thousands of videos, we have a plan that fits your needs.

All plans include access to our full API, support for all subtitle formats, and processing of both manual and auto-generated captions.`,
    ctaText: "Get Started Free",
    relatedPages: [
      { title: "API Documentation", href: "/docs" },
      { title: "About", href: "/about" },
      { title: "Batch Downloader", href: "/tools/batch-downloader" },
    ],
    faqs: [
      {
        question: "Is the free tier really free?",
        answer:
          "Yes! The free tier includes 1,000 API requests per day at no cost. No credit card required. It's perfect for personal projects, testing, and small-scale applications.",
      },
      {
        question: "What happens if I exceed my plan limits?",
        answer:
          "API requests beyond your plan limit will return a 429 status with a Retry-After header. You can upgrade anytime or wait for your daily quota to reset.",
      },
      {
        question: "Can I change plans at any time?",
        answer:
          "Yes! You can upgrade or downgrade your plan at any time. Upgrades take effect immediately. Downgrades apply at the start of your next billing cycle.",
      },
      {
        question: "Do you offer refunds?",
        answer:
          "We offer a 30-day money-back guarantee for paid plans. If you're not satisfied, contact support for a full refund.",
      },
      {
        question: "What payment methods do you accept?",
        answer:
          "We accept all major credit cards (Visa, MasterCard, American Express) and PayPal. Enterprise customers can pay via invoice with NET 30 terms.",
      },
      {
        question: "Do you offer discounts for nonprofits or education?",
        answer:
          "Yes! We offer special pricing for qualified nonprofits, educational institutions, and open-source projects. Contact us for details.",
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
