---
name: seo-crawlability
description: "Use whenever building or reviewing marketing/landing pages intended for entrepeai.com's public site — audit and improve meta tags, structured data, social previews (OpenGraph/Twitter cards), sitemap.xml, robots.txt, and rendering strategy for search-engine crawlability. Trigger this proactively any time a new public-facing landing/marketing page is added, not just when the user explicitly says 'SEO'. Do NOT trigger for admin-rbac, tenant-admin, review, files, or signin pages — those are authenticated app screens behind auth, not indexed public pages, so SEO does not apply to them."
---

# SEO & Crawlability

Marketing/landing pages for entrepeai.com are public and need to rank and preview correctly. This is a different concern from `apps/frontend`'s existing authenticated screens (admin-rbac, files, review, signin, tenant-admin) — those are behind login and should generally NOT be indexed (verify `noindex` is set on them, don't add SEO tooling there).

## The rendering-strategy decision comes first

`apps/frontend` today is a CSR-only Vite multi-page app (`admin-rbac.html`, `files.html`, `home.html`, `review.html`, `share.html`, `signin.html`, `tenant-admin.html` per `vite.config.ts` entries). Client-side-rendered React is weak for SEO: crawlers that don't execute JS see an empty shell, and social-preview scrapers (Slack, X, LinkedIn) almost never execute JS, so OpenGraph tags injected client-side won't show up in link previews.

Before doing any on-page SEO work, confirm with the user whether marketing pages will:
- **(a)** live in the same CSR Vite app (simplest, but requires prerendering or static HTML generation to get real SEO), or
- **(b)** live in a separate statically-generated/SSR site.

Don't assume — this was flagged as an open decision earlier and materially changes what "SEO work" even means here. If unresolved, ask before recommending a rendering-strategy fix.

## What to check once rendering strategy is settled

1. **Per-page meta tags** — unique `<title>` and `<meta name="description">` per landing page (not one shared shell title across all pages — check the relevant `.html` entry point).
2. **OpenGraph / Twitter Card tags** — `og:title`, `og:description`, `og:image` (absolute URL, real dimensions), `twitter:card`. These must be present in the initial HTML response, not injected after hydration, per the rendering-strategy note above.
3. **Structured data** — JSON-LD (`Organization`, `WebSite`, `BreadcrumbList` as applicable) matching what's actually on the page — never fabricate schema fields that don't reflect real content.
4. **`robots.txt`** — allow public marketing paths, disallow authenticated app routes (admin-rbac, tenant-admin, review, files, signin) if they're reachable at crawlable URLs.
5. **`sitemap.xml`** — lists only public marketing/landing URLs, kept in sync as pages are added — check whether this is hand-maintained or needs a build-time generation step.
6. **Core Web Vitals impact** — largest-contentful-paint and cumulative-layout-shift are ranking factors; hand this off to `performance-optimization` rather than duplicating that work here.

## Verification

Don't just read the HTML source for tag presence — fetch the page as a crawler would (view-source / curl the built output, not the dev-server-hydrated DOM) to confirm tags are actually in the server-delivered HTML, since that's the gap CSR most commonly creates.
