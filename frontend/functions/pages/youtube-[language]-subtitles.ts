import { generateHtml, LANGUAGE_PAGES } from "./_template";
import type { PagesFunction } from "@cloudflare/workers-types";

interface LanguageConfig {
  name: string;
  code: string;
  title: string;
  description: string;
  keywords: string[];
  content: string;
  faqs: Array<{ question: string; answer: string }>;
}

const LANGUAGE_CONFIGS: Record<string, LanguageConfig> = {
  english: {
    name: "English",
    code: "en",
    title:
      "Download English YouTube Subtitles - Free English Caption Extractor",
    description:
      "Extract and download English subtitles from YouTube videos. Support for both manual and auto-generated English captions. Download as SRT, VTT, or TXT format.",
    keywords: [
      "youtube english subtitles",
      "english captions youtube",
      "download english subtitles",
      "youtube english captions",
      "extract english subtitles",
      "english transcript youtube",
    ],
    content: `Download English subtitles and captions from any YouTube video. Our tool supports both manually uploaded English subtitles and YouTube's auto-generated English captions, giving you comprehensive coverage for English content.

English is the most widely supported language on YouTube, with nearly every video featuring either manual or auto-generated English captions. Use our tool to extract these captions in your preferred format - whether you need SRT files for video editing, VTT for web players, or plain text transcripts for content analysis.`,
    faqs: [
      {
        question: "Are English subtitles available on all YouTube videos?",
        answer:
          "Most popular videos have English subtitles available. YouTube's auto-caption feature also generates English captions for many videos, even if they weren't manually uploaded.",
      },
      {
        question:
          "What's the difference between manual and auto-generated English subtitles?",
        answer:
          "Manual subtitles are created by the video creator and are typically more accurate with proper punctuation and timing. Auto-generated subtitles use speech recognition and may have some errors.",
      },
      {
        question: "Can I extract English captions from non-English videos?",
        answer:
          "Yes! Many non-English videos have English translations available as subtitles, or YouTube may auto-generate English captions using translation.",
      },
    ],
  },
  spanish: {
    name: "Spanish",
    code: "es",
    title:
      "Download Spanish YouTube Subtitles - Extract Spanish Captions (Espanol)",
    description:
      "Extract and download Spanish subtitles from YouTube videos. Get both manual and auto-generated Spanish captions (subtitulos en espanol). Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube spanish subtitles",
      "subtitulos youtube",
      "descargar subtitulos",
      "spanish captions youtube",
      "extract spanish subtitles",
      "youtube en espanol",
    ],
    content: `Descarga subtitulos en espanol de cualquier video de YouTube. Nuestra herramienta admite tanto subtitulos manuales como los generados automaticamente por YouTube, dandote cobertura completa para contenido en espanol.

Los subtitulos en espanol estan disponibles en millones de videos de YouTube, desde contenido educativo hasta entretenimiento. Extrae estos subtitulos en tu formato preferido - archivos SRT para edicion de video, VTT para reproductores web, o texto plano para analisis de contenido.`,
    faqs: [
      {
        question:
          "?Estan disponibles los subtitulos en espanol en todos los videos?",
        answer:
          "Muchos videos populares tienen subtitulos en espanol disponibles. YouTube tambien genera subtitulos automaticos en espanol para muchos videos.",
      },
      {
        question: "?Puedo usar los subtitulos para aprender espanol?",
        answer:
          "!Absolutamente! Los subtitulos en espanol son excelentes para practicar el idioma. Puedes usarlos junto con el audio para mejorar tu comprension.",
      },
    ],
  },
  french: {
    name: "French",
    code: "fr",
    title:
      "Download French YouTube Subtitles - Extract French Captions (Francais)",
    description:
      "Extract and download French subtitles from YouTube videos. Get both manual and auto-generated French captions (sous-titres francais). Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube french subtitles",
      "sous-titres youtube",
      "telecharger sous-titres",
      "french captions youtube",
      "extract french subtitles",
      "youtube francais",
    ],
    content: `Download French subtitles and captions from YouTube videos. Our tool extracts both manually uploaded French subtitles (sous-titres) and YouTube's auto-generated French captions, covering the vast library of French content on YouTube.

French subtitles are widely available on educational content, movies, TV shows, and music videos on YouTube. Extract them in SRT, VTT, or plain text format for use in video projects, language learning, or content translation.`,
    faqs: [
      {
        question: "Are French subtitles accurate?",
        answer:
          "Manual French subtitles created by content creators are highly accurate. Auto-generated subtitles are quite good but may have occasional errors with homophones or proper names.",
      },
      {
        question: "Can I use French subtitles for language learning?",
        answer:
          "Yes! French subtitles are excellent for language learning. You can use them to practice reading comprehension and expand your vocabulary.",
      },
    ],
  },
  german: {
    name: "German",
    code: "de",
    title:
      "Download German YouTube Subtitles - Extract German Captions (Deutsch)",
    description:
      "Extract and download German subtitles from YouTube videos. Get both manual and auto-generated German captions (Untertitel). Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube german subtitles",
      "untertitel youtube",
      "deutsche untertitel",
      "german captions youtube",
      "extract german subtitles",
      "youtube deutsch",
    ],
    content: `Download German subtitles and captions from YouTube videos. Our tool supports both manually created German subtitles (Untertitel) and YouTube's auto-generated German captions for comprehensive coverage of German content.

German is well-supported on YouTube with excellent auto-caption capabilities. Extract these subtitles for video projects, language learning, or content adaptation.`,
    faqs: [
      {
        question: "Does YouTube auto-generate German captions?",
        answer:
          "Yes, YouTube's speech recognition supports German and automatically generates captions for many videos, even if manual subtitles weren't uploaded.",
      },
    ],
  },
  portuguese: {
    name: "Portuguese",
    code: "pt",
    title:
      "Download Portuguese YouTube Subtitles - Extract Portuguese Captions",
    description:
      "Extract and download Portuguese subtitles from YouTube videos. Support for both Brazilian and European Portuguese (legendas). Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube portuguese subtitles",
      "legendas youtube",
      "baixar legendas",
      "portuguese captions youtube",
      "extract portuguese subtitles",
    ],
    content: `Download Portuguese subtitles from YouTube videos. Our tool extracts both Brazilian Portuguese (pt-BR) and European Portuguese (pt-PT) subtitles, whether manually uploaded or auto-generated by YouTube.

Portuguese subtitles are widely available on music videos, educational content, and entertainment from Portuguese-speaking countries around the world.`,
    faqs: [
      {
        question:
          "What's the difference between Brazilian and European Portuguese subtitles?",
        answer:
          "They differ in spelling, vocabulary, and some grammar. YouTube often provides both options when available.",
      },
    ],
  },
  japanese: {
    name: "Japanese",
    code: "ja",
    title: "Download Japanese YouTube Subtitles - Extract Japanese Captions",
    description:
      "Extract and download Japanese subtitles from YouTube videos. Get both manual and auto-generated Japanese captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube japanese subtitles",
      "japanese captions youtube",
      "download japanese subtitles",
      "extract japanese subtitles",
      "youtube japanese",
    ],
    content: `Download Japanese subtitles and captions from YouTube videos. Extract both manually uploaded Japanese subtitles and auto-generated captions from YouTube's speech recognition system.

Japanese content on YouTube includes anime, dramas, educational content, and music videos with comprehensive subtitle support.`,
    faqs: [
      {
        question: "Do Japanese subtitles include furigana?",
        answer:
          "Standard subtitle files don't include furigana (reading aids), but the text content is plain Japanese characters that can be used with furigana generators.",
      },
    ],
  },
  korean: {
    name: "Korean",
    code: "ko",
    title: "Download Korean YouTube Subtitles - Extract Korean Captions",
    description:
      "Extract and download Korean subtitles from YouTube videos. Get both manual and auto-generated Korean captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube korean subtitles",
      "korean captions youtube",
      "download korean subtitles",
      "extract korean subtitles",
    ],
    content: `Download Korean subtitles and captions from YouTube videos. Our tool extracts both manual Korean subtitles and auto-generated captions, covering K-pop, K-dramas, and educational content.`,
    faqs: [],
  },
  chinese: {
    name: "Chinese",
    code: "zh",
    title: "Download Chinese YouTube Subtitles - Extract Chinese Captions",
    description:
      "Extract and download Chinese subtitles from YouTube videos. Support for both Simplified and Traditional Chinese. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube chinese subtitles",
      "chinese captions youtube",
      "download chinese subtitles",
      "extract chinese subtitles",
    ],
    content: `Download Chinese subtitles from YouTube videos. Our tool supports both Simplified Chinese (zh-CN) and Traditional Chinese (zh-TW) subtitles, covering the vast library of Chinese content on YouTube.`,
    faqs: [
      {
        question:
          "Can I get both Simplified and Traditional Chinese subtitles?",
        answer:
          "Yes, when both are available, you can select either Simplified or Traditional Chinese from the language options.",
      },
    ],
  },
  russian: {
    name: "Russian",
    code: "ru",
    title: "Download Russian YouTube Subtitles - Extract Russian Captions",
    description:
      "Extract and download Russian subtitles from YouTube videos. Get both manual and auto-generated Russian captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube russian subtitles",
      "russian captions youtube",
      "download russian subtitles",
      "extract russian subtitles",
    ],
    content: `Download Russian subtitles from YouTube videos. Extract both manually uploaded Russian subtitles and auto-generated captions for comprehensive coverage of Russian content.`,
    faqs: [],
  },
  italian: {
    name: "Italian",
    code: "it",
    title: "Download Italian YouTube Subtitles - Extract Italian Captions",
    description:
      "Extract and download Italian subtitles from YouTube videos. Get both manual and auto-generated Italian captions (sottotitoli). Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube italian subtitles",
      "sottotitoli youtube",
      "italian captions youtube",
      "download italian subtitles",
    ],
    content: `Download Italian subtitles from YouTube videos. Extract both manual Italian subtitles and auto-generated captions covering educational content, entertainment, and more.`,
    faqs: [],
  },
  arabic: {
    name: "Arabic",
    code: "ar",
    title: "Download Arabic YouTube Subtitles - Extract Arabic Captions",
    description:
      "Extract and download Arabic subtitles from YouTube videos. Get both manual and auto-generated Arabic captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube arabic subtitles",
      "arabic captions youtube",
      "download arabic subtitles",
      "extract arabic subtitles",
    ],
    content: `Download Arabic subtitles from YouTube videos. Extract both manually uploaded Arabic subtitles and auto-generated captions for comprehensive coverage of Arabic content.`,
    faqs: [],
  },
  hindi: {
    name: "Hindi",
    code: "hi",
    title: "Download Hindi YouTube Subtitles - Extract Hindi Captions",
    description:
      "Extract and download Hindi subtitles from YouTube videos. Get both manual and auto-generated Hindi captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube hindi subtitles",
      "hindi captions youtube",
      "download hindi subtitles",
      "extract hindi subtitles",
    ],
    content: `Download Hindi subtitles from YouTube videos. Extract both manual Hindi subtitles and auto-generated captions covering Bollywood content, educational videos, and entertainment.`,
    faqs: [],
  },
  dutch: {
    name: "Dutch",
    code: "nl",
    title: "Download Dutch YouTube Subtitles - Extract Dutch Captions",
    description:
      "Extract and download Dutch subtitles from YouTube videos. Get both manual and auto-generated Dutch captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube dutch subtitles",
      "dutch captions youtube",
      "download dutch subtitles",
      "extract dutch subtitles",
    ],
    content: `Download Dutch subtitles from YouTube videos. Extract both manual Dutch subtitles and auto-generated captions for comprehensive coverage.`,
    faqs: [],
  },
  turkish: {
    name: "Turkish",
    code: "tr",
    title: "Download Turkish YouTube Subtitles - Extract Turkish Captions",
    description:
      "Extract and download Turkish subtitles from YouTube videos. Get both manual and auto-generated Turkish captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube turkish subtitles",
      "turkish captions youtube",
      "download turkish subtitles",
      "extract turkish subtitles",
    ],
    content: `Download Turkish subtitles from YouTube videos. Extract both manual Turkish subtitles and auto-generated captions.`,
    faqs: [],
  },
  vietnamese: {
    name: "Vietnamese",
    code: "vi",
    title:
      "Download Vietnamese YouTube Subtitles - Extract Vietnamese Captions",
    description:
      "Extract and download Vietnamese subtitles from YouTube videos. Get both manual and auto-generated Vietnamese captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube vietnamese subtitles",
      "vietnamese captions youtube",
      "download vietnamese subtitles",
      "extract vietnamese subtitles",
    ],
    content: `Download Vietnamese subtitles from YouTube videos. Extract both manual Vietnamese subtitles and auto-generated captions.`,
    faqs: [],
  },
  thai: {
    name: "Thai",
    code: "th",
    title: "Download Thai YouTube Subtitles - Extract Thai Captions",
    description:
      "Extract and download Thai subtitles from YouTube videos. Get both manual and auto-generated Thai captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube thai subtitles",
      "thai captions youtube",
      "download thai subtitles",
      "extract thai subtitles",
    ],
    content: `Download Thai subtitles from YouTube videos. Extract both manual Thai subtitles and auto-generated captions.`,
    faqs: [],
  },
  indonesian: {
    name: "Indonesian",
    code: "id",
    title:
      "Download Indonesian YouTube Subtitles - Extract Indonesian Captions",
    description:
      "Extract and download Indonesian subtitles from YouTube videos. Get both manual and auto-generated Indonesian captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube indonesian subtitles",
      "indonesian captions youtube",
      "download indonesian subtitles",
      "extract indonesian subtitles",
    ],
    content: `Download Indonesian subtitles from YouTube videos. Extract both manual Indonesian subtitles and auto-generated captions.`,
    faqs: [],
  },
  swedish: {
    name: "Swedish",
    code: "sv",
    title: "Download Swedish YouTube Subtitles - Extract Swedish Captions",
    description:
      "Extract and download Swedish subtitles from YouTube videos. Get both manual and auto-generated Swedish captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube swedish subtitles",
      "swedish captions youtube",
      "download swedish subtitles",
      "extract swedish subtitles",
    ],
    content: `Download Swedish subtitles from YouTube videos. Extract both manual Swedish subtitles and auto-generated captions.`,
    faqs: [],
  },
  polish: {
    name: "Polish",
    code: "pl",
    title: "Download Polish YouTube Subtitles - Extract Polish Captions",
    description:
      "Extract and download Polish subtitles from YouTube videos. Get both manual and auto-generated Polish captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube polish subtitles",
      "polish captions youtube",
      "download polish subtitles",
      "extract polish subtitles",
    ],
    content: `Download Polish subtitles from YouTube videos. Extract both manual Polish subtitles and auto-generated captions.`,
    faqs: [],
  },
  czech: {
    name: "Czech",
    code: "cs",
    title: "Download Czech YouTube Subtitles - Extract Czech Captions",
    description:
      "Extract and download Czech subtitles from YouTube videos. Get both manual and auto-generated Czech captions. Download as SRT, VTT, or TXT.",
    keywords: [
      "youtube czech subtitles",
      "czech captions youtube",
      "download czech subtitles",
      "extract czech subtitles",
    ],
    content: `Download Czech subtitles from YouTube videos. Extract both manual Czech subtitles and auto-generated captions.`,
    faqs: [],
  },
};

// Default config for languages without specific overrides
function getDefaultConfig(name: string, code: string): LanguageConfig {
  return {
    name,
    code,
    title: `Download ${name} YouTube Subtitles - Extract ${name} Captions`,
    description: `Extract and download ${name} subtitles from YouTube videos. Get both manual and auto-generated ${name} captions. Download as SRT, VTT, or TXT.`,
    keywords: [
      `youtube ${name.toLowerCase()} subtitles`,
      `${name.toLowerCase()} captions youtube`,
      `download ${name.toLowerCase()} subtitles`,
      `extract ${name.toLowerCase()} subtitles`,
    ],
    content: `Download ${name} subtitles from YouTube videos. Our tool extracts both manually uploaded ${name} subtitles and YouTube's auto-generated ${name} captions, providing comprehensive coverage for ${name} content.`,
    faqs: [
      {
        question: `Are ${name} subtitles available on YouTube?`,
        answer: `Yes, YouTube supports ${name} subtitles through manual uploads and auto-generation for many videos.`,
      },
    ],
  };
}

export const onRequest: PagesFunction = async ({ request, params }) => {
  const origin = new URL(request.url).origin;
  const path = new URL(request.url).pathname;

  // Extract language from URL path (youtube-{language}-subtitles)
  const match = path.match(/youtube-([a-z]+)-subtitles/);
  if (!match) {
    return new Response("Not found", { status: 404 });
  }

  const languageSlug = match[1];
  const config =
    LANGUAGE_CONFIGS[languageSlug] ||
    getDefaultConfig(languageSlug, languageSlug.slice(0, 2).toLowerCase());

  const relatedPages = [
    { title: "YouTube to SRT", href: "/youtube-to-srt" },
    { title: "YouTube to VTT", href: "/youtube-to-vtt" },
    { title: "YouTube English Subtitles", href: "/youtube-english-subtitles" },
    {
      title: "Subtitle Downloader",
      href: "/tools/youtube-subtitle-downloader",
    },
  ];

  const pageConfig = {
    title: config.title,
    description: config.description,
    keywords: config.keywords,
    heading: `${config.name} YouTube Subtitle Extractor`,
    subheading: `Download ${config.name} subtitles from any YouTube video`,
    content: config.content,
    ctaText: `Extract ${config.name} Subtitles`,
    relatedPages,
    faqs: config.faqs,
  };

  const html = generateHtml(pageConfig, origin, path);

  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=UTF-8",
      "Cache-Control": "public, max-age=86400",
    },
  });
};
