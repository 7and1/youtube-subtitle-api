import type { PagesFunction } from "@cloudflare/workers-types";

/**
 * Robots.txt Generator
 * Controls crawler access and points to sitemap
 */
export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const body = `# Allow all crawlers
User-agent: *
Allow: /

# Crawl-delay for respectful crawling
Crawl-delay: 1

# Disallow API endpoints (for bots, not users)
Disallow: /api/
Disallow: /health
Disallow: /metrics

# Sitemap location
Sitemap: ${origin}/sitemap.xml
`;
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=UTF-8",
      "Cache-Control": "public, max-age=86400",
    },
  });
};
