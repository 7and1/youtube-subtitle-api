/**
 * SEO Page Template Generator
 * Shared utilities for programmatic SEO pages
 */

export interface PageConfig {
  title: string;
  description: string;
  keywords: string[];
  heading: string;
  subheading: string;
  content: string;
  ctaText: string;
  relatedPages: Array<{ title: string; href: string }>;
  faqs: Array<{ question: string; answer: string }>;
}

export const LANGUAGE_PAGES: Array<{
  code: string;
  name: string;
  nativeName?: string;
}> = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish", nativeName: "Espanol" },
  { code: "fr", name: "French", nativeName: "Francais" },
  { code: "de", name: "German", nativeName: "Deutsch" },
  { code: "pt", name: "Portuguese", nativeName: "Portugues" },
  { code: "it", name: "Italian", nativeName: "Italiano" },
  { code: "ru", name: "Russian", nativeName: "Russkiy" },
  { code: "ja", name: "Japanese", nativeName: "Nihongo" },
  { code: "ko", name: "Korean", nativeName: "Hangug" },
  { code: "zh", name: "Chinese", nativeName: "Zhongwen" },
  { code: "ar", name: "Arabic", nativeName: "Arabiya" },
  { code: "hi", name: "Hindi", nativeName: "Hindi" },
  { code: "nl", name: "Dutch", nativeName: "Nederlands" },
  { code: "pl", name: "Polish", nativeName: "Polski" },
  { code: "tr", name: "Turkish", nativeName: "Turkce" },
  { code: "vi", name: "Vietnamese", nativeName: "Tieng Viet" },
  { code: "th", name: "Thai", nativeName: "Phasa Thai" },
  { code: "id", name: "Indonesian", nativeName: "Bahasa Indonesia" },
  { code: "sv", name: "Swedish", nativeName: "Svenska" },
  { code: "cs", name: "Czech", nativeName: "Cestina" },
];

export const FORMAT_PAGES: Array<{
  slug: string;
  name: string;
  extension: string;
  description: string;
}> = [
  {
    slug: "youtube-to-srt",
    name: "SRT",
    extension: ".srt",
    description: "SubRip format compatible with most video players",
  },
  {
    slug: "youtube-to-vtt",
    name: "VTT",
    extension: ".vtt",
    description: "WebVTT format for HTML5 video players",
  },
  {
    slug: "youtube-to-txt",
    name: "TXT",
    extension: ".txt",
    description: "Plain text transcript for analysis and documentation",
  },
];

export function generateHtml(
  config: PageConfig,
  origin: string,
  path: string,
): string {
  const {
    title,
    description,
    keywords,
    heading,
    subheading,
    content,
    ctaText,
    relatedPages,
    faqs,
  } = config;

  const keywordsStr = keywords.join(", ");
  const relatedLinks = relatedPages
    .map((page) => `<li><a href="${page.href}">${page.title}</a></li>`)
    .join("\n          ");

  const faqJson = faqs
    .map(
      (faq) => `
            {
              "@type": "Question",
              "name": "${escapeJson(faq.question)}",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "${escapeJson(faq.answer)}"
              }
            }`,
    )
    .join(",");

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(title)}</title>
    <meta name="description" content="${escapeHtml(description)}" />
    <meta name="keywords" content="${escapeHtml(keywordsStr)}" />
    <meta name="author" content="YouTube Subtitle API" />
    <meta name="robots" content="index, follow" />

    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="canonical" href="${origin}${path}" />

    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="YouTube Subtitle API" />
    <meta property="og:title" content="${escapeHtml(title)}" />
    <meta property="og:description" content="${escapeHtml(description)}" />
    <meta property="og:url" content="${origin}${path}" />
    <meta property="og:image" content="${origin}/og.svg" />
    <meta property="og:locale" content="en_US" />

    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${escapeHtml(title)}" />
    <meta name="twitter:description" content="${escapeHtml(description)}" />
    <meta name="twitter:image" content="${origin}/og.svg" />

    <link rel="alternate" hreflang="en" href="${origin}${path}" />
    <link rel="alternate" hreflang="x-default" href="${origin}${path}" />

    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebPage",
          "@id": "${origin}${path}#webpage",
          "url": "${origin}${path}",
          "name": "${escapeJson(title)}",
          "description": "${escapeJson(description)}",
          "isPartOf": {
            "@id": "${origin}/#website"
          }
        },
        {
          "@type": "FAQPage",
          "mainEntity": [${faqJson}]
        }
      ]
    }
    </script>

    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        line-height: 1.6;
        color: #333;
        background: #f5f5f5;
      }
      .container { max-width: 900px; margin: 0 auto; padding: 20px; }
      header {
        background: linear-gradient(135deg, #ff0000 0%, #cc0000 100%);
        color: white;
        padding: 40px 20px;
        text-align: center;
        margin-bottom: 30px;
      }
      h1 { font-size: 2.5rem; margin-bottom: 10px; }
      .subtitle { font-size: 1.1rem; opacity: 0.9; }
      .card {
        background: white;
        border-radius: 8px;
        padding: 30px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      }
      h2 { color: #ff0000; margin-bottom: 20px; font-size: 1.8rem; }
      h3 { color: #333; margin-bottom: 15px; margin-top: 25px; font-size: 1.3rem; }
      p { margin-bottom: 15px; line-height: 1.8; }
      .cta-container { text-align: center; margin: 30px 0; }
      .btn {
        display: inline-block;
        background: #ff0000;
        color: white;
        padding: 15px 40px;
        border-radius: 5px;
        text-decoration: none;
        font-weight: bold;
        font-size: 1.1rem;
        transition: background 0.3s;
      }
      .btn:hover { background: #cc0000; }
      .features {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin: 30px 0;
      }
      .feature {
        background: #f9f9f9;
        padding: 20px;
        border-radius: 5px;
        border-left: 4px solid #ff0000;
      }
      .feature h4 { color: #ff0000; margin-bottom: 10px; }
      .related-pages {
        background: #f0f0f0;
        padding: 20px;
        border-radius: 5px;
        margin-top: 30px;
      }
      .related-pages ul {
        list-style: none;
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
      }
      .related-pages a {
        color: #ff0000;
        text-decoration: none;
        font-weight: 500;
      }
      .related-pages a:hover { text-decoration: underline; }
      .faq-item {
        border-bottom: 1px solid #eee;
        padding: 20px 0;
      }
      .faq-item:last-child { border-bottom: none; }
      .faq-question {
        font-weight: bold;
        color: #333;
        margin-bottom: 10px;
        font-size: 1.1rem;
      }
      footer {
        text-align: center;
        padding: 30px 20px;
        color: #666;
        font-size: 0.9rem;
      }
      @media (max-width: 600px) {
        h1 { font-size: 1.8rem; }
        .card { padding: 20px; }
      }
    </style>
  </head>
  <body>
    <header>
      <div class="container">
        <h1>${escapeHtml(heading)}</h1>
        <p class="subtitle">${escapeHtml(subheading)}</p>
      </div>
    </header>

    <main class="container">
      <div class="card">
        <p>${content}</p>
        <div class="cta-container">
          <a href="/" class="btn">${escapeHtml(ctaText)}</a>
        </div>
      </div>

      <div class="card">
        <h2>Features</h2>
        <div class="features">
          <div class="feature">
            <h4>Free Forever</h4>
            <p>No registration or payment required. Extract unlimited subtitles.</p>
          </div>
          <div class="feature">
            <h4>100+ Languages</h4>
            <p>Support for all YouTube languages including auto-generated captions.</p>
          </div>
          <div class="feature">
            <h4>Fast API</h4>
            <p>Production-grade API with caching and rate limiting.</p>
          </div>
          <div class="feature">
            <h4>Multiple Formats</h4>
            <p>Export as SRT, VTT, or plain text for any use case.</p>
          </div>
        </div>
      </div>

      ${
        faqs.length > 0
          ? `
      <div class="card">
        <h2>Frequently Asked Questions</h2>
        ${faqs
          .map(
            (faq) => `
          <div class="faq-item">
            <div class="faq-question">${escapeHtml(faq.question)}</div>
            <p>${escapeHtml(faq.answer)}</p>
          </div>
        `,
          )
          .join("\n        ")}
      </div>
      `
          : ""
      }

      <div class="related-pages">
        <h3>Related Tools</h3>
        <ul>
          ${relatedLinks}
        </ul>
      </div>
    </main>

    <footer>
      <p>© ${new Date().getFullYear()} YouTube Subtitle API. Free online subtitle extraction tool.</p>
      <p><a href="/">Home</a> • <a href="/docs">API Documentation</a> • <a href="/pricing">Pricing</a> • <a href="/about">About</a></p>
    </footer>
  </body>
</html>`;
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

function escapeJson(text: string): string {
  return text.replace(/"/g, '\\"').replace(/\n/g, "\\n");
}

export function getSitemapEntries(origin: string): Array<{
  loc: string;
  lastmod?: string;
  priority?: number;
  changefreq?: string;
}> {
  const entries: Array<{
    loc: string;
    lastmod?: string;
    priority?: number;
    changefreq?: string;
  }> = [
    { loc: origin + "/", priority: 1.0, changefreq: "daily" },
    { loc: origin + "/docs", priority: 0.8, changefreq: "weekly" },
    { loc: origin + "/pricing", priority: 0.7, changefreq: "monthly" },
    { loc: origin + "/about", priority: 0.5, changefreq: "monthly" },
  ];

  // Format pages
  for (const format of FORMAT_PAGES) {
    entries.push({
      loc: origin + "/" + format.slug,
      priority: 0.9,
      changefreq: "weekly",
    });
  }

  // Language pages
  for (const lang of LANGUAGE_PAGES) {
    entries.push({
      loc: origin + "/youtube-" + lang.name.toLowerCase() + "-subtitles",
      priority: 0.8,
      changefreq: "weekly",
    });
  }

  // Tool pages
  entries.push({
    loc: origin + "/tools/youtube-subtitle-downloader",
    priority: 0.9,
    changefreq: "weekly",
  });
  entries.push({
    loc: origin + "/tools/batch-downloader",
    priority: 0.7,
    changefreq: "monthly",
  });

  return entries;
}
