import { SITE_URL } from "@/lib/api";

// Hand-rolled rather than Next's MetadataRoute.Robots (app/robots.ts, which
// this replaces): that helper only emits the directives it knows about, and
// there is no way to add a Content-Signal line through it. Everything below
// reproduces the previous output exactly, plus the signal block.
export const dynamic = "force-static";
export const revalidate = 3600;

// Content Signals (contentsignals.org) — a machine-readable statement of how
// this site's content may be reused, expressed in the robots.txt the crawlers
// already fetch. Non-binding, but it is the declaration operators are starting
// to honour, and silence is not consent-neutral: it is read as "no preference".
//
// The values are a deliberate business choice, not a default:
//   search    = yes  appear in search indexes and results
//   ai-input  = yes  may be retrieved and cited when an AI answers a question
//   ai-train  = no   may NOT be used as model training data
//
// ai-input=yes is the whole point of the identity work in lib/schema.ts: an
// assistant asked "who supplies industrial chemicals in Nairobi" can only name
// Karivex if it is permitted to read and cite these pages. That permission is
// what drives referrals, and it is unaffected by the line below.
//
// ai-train was set to `no` by the owner on 2026-08-07, reversing the earlier
// default. The two are genuinely separable: retrieval-and-cite sends a buyer
// back to this site, training absorbs the catalogue into a model that will
// answer without ever naming the source. Keeping ai-input=yes preserves every
// visibility benefit; ai-train=no declines the one that returns nothing.
// This is a declaration, not an enforcement mechanism — it is honoured by
// operator good faith, so it is not a substitute for anything technical.
const CONTENT_SIGNAL = "search=yes, ai-input=yes, ai-train=no";

const DISALLOW = [
  "/api/",
  "/admin/",
  // Next.js <Link> prefetching appends ?_rsc=<hash> to fetch the React Server
  // Component payload. Googlebot executes those prefetches while rendering,
  // discovers the URLs, and then crawls them as ordinary pages — they return a
  // full duplicate of the HTML, one distinct URL per hash. In the last 7 days
  // of access logs 450 of 470 verified Googlebot requests (96%) went to ?_rsc=
  // URLs, leaving ~20 for the 225 real pages. These are never destinations, so
  // blocking them costs nothing and hands the entire crawl budget back.
  "/*?_rsc=",
  "/*&_rsc=",
];

// Training-only crawlers, denied outright. The Content-Signal above is a
// declaration honoured by good faith; these blocks are the part with teeth,
// and without them `ai-train=no` changes nothing in practice.
//
// The split below is the whole point, and it is not "AI bots" vs "not AI bots":
// each of these operators runs SEPARATE crawlers for training and for
// answering a user's question, and only the training half is listed here.
// Blocking these does NOT remove Karivex from AI answers — the retrieval
// crawlers that produce a cited, clickable mention are all still allowed
// (OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot),
// and neither Googlebot nor Bingbot is touched, so organic search ranking is
// unaffected. Google documents explicitly that Google-Extended has no bearing
// on Search.
//
// The real cost, stated plainly: a model trained after today learns less about
// this company from these pages. That is the trade being made deliberately —
// citation-with-a-referral is kept, absorption-without-attribution is declined.
const NO_TRAIN_AGENTS = [
  "GPTBot",                 // OpenAI, model training (NOT OAI-SearchBot)
  "Google-Extended",        // Gemini/Vertex training; no effect on Search
  "Applebot-Extended",      // Apple Intelligence training (NOT Applebot)
  "ClaudeBot",              // Anthropic training (NOT Claude-SearchBot)
  "anthropic-ai",           // legacy Anthropic token
  "Claude-Web",             // legacy Anthropic token
  "meta-externalagent",     // Meta AI training
  "FacebookBot",            // Meta language-model training
  "CCBot",                  // Common Crawl — the corpus most others train from
  "Bytespider",             // ByteDance
  "Amazonbot",              // Amazon model training
  "Diffbot",
  "Omgilibot",
  "PanguBot",
  "Timpibot",
  "Webzio-Extended",
  "ImagesiftBot",
  "AI2Bot",
  "cohere-ai",
  "cohere-training-data-crawler",
];

export function GET(): Response {
  const body = [
    "User-agent: *",
    `Content-Signal: ${CONTENT_SIGNAL}`,
    "Allow: /",
    ...DISALLOW.map((p) => `Disallow: ${p}`),
    "",
    // One group per agent rather than a shared group: a crawler only ever obeys
    // the single most specific User-agent group that matches it, so listing
    // several agents above one Disallow works, but a stacked group is the
    // easier form to get subtly wrong when editing later.
    ...NO_TRAIN_AGENTS.flatMap((agent) => [`User-agent: ${agent}`, "Disallow: /", ""]),
    `Sitemap: ${SITE_URL}/sitemap.xml`,
    "",
  ].join("\n");

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
