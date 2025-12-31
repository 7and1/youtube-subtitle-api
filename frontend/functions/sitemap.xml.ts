import { getSitemapEntries } from "./pages/_template";
import type { PagesFunction } from "@cloudflare/workers-types";

/**
 * Dynamic Sitemap Generator
 * Includes all programmatic SEO pages with proper priorities and change frequencies
 */
export const onRequest: PagesFunction = async ({ request }) => {
  const origin = new URL(request.url).origin;
  const entries = getSitemapEntries(origin);
  const lastmod = new Date().toISOString().split("T")[0];

  const urlEntries = entries
    .map(
      (entry) => `  <url>
    <loc>${entry.loc}</loc>
    <lastmod>${entry.lastmod || lastmod}</lastmod>
    <changefreq>${entry.changefreq || "weekly"}</changefreq>
    <priority>${entry.priority || 0.5}</priority>
  </url>`,
    )
    .join("\n");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">
${urlEntries}
</urlset>`;

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "application/xml; charset=UTF-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};
