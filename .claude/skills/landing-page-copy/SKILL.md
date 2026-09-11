---
name: landing-page-copy
description: "Use whenever writing or reviewing copy and content structure for marketing/landing pages on entrepeai.com — hero messaging, value proposition, social proof placement, feature sections, and call-to-action design, evaluated for information architecture and conversion, not just grammar. Trigger this proactively whenever the user is drafting landing-page content, a marketing page layout, or asks things like 'write copy for X page' or 'what should this page say', even without the words 'copywriting' or 'conversion' being used."
---

# Landing Page Copy & Structure

This is about information architecture and persuasion structure for entrepeai.com's public marketing pages — a different concern from `frontend-ui-engineering` (component implementation) or `design-system-consistency` (visual tokens). A landing page can be pixel-perfect and still fail if the copy doesn't answer "what is this, who's it for, why should I believe it, what do I do next" in that rough order.

## Structure to check for, in priority order

1. **Hero section** — one sentence that states what the product does and for whom, not a vague mission statement. Given this platform's actual direction (document intelligence, workflow automation, AI-enabled services per this repo's architectural direction), hero copy should name a concrete capability or outcome, not generic AI-platform language that could describe any competitor.
2. **Value proposition** — the "why this, why now, why us" — should map to real differentiators, not invented ones. Don't fabricate customer counts, benchmarks, or claims not backed by something the user has confirmed is true.
3. **Social proof placement** — testimonials, logos, or metrics belong close to the decision point (near a CTA or pricing section), not buried at the page bottom where they can't influence the decision.
4. **Feature sections** — lead with the outcome/benefit, not the mechanism; "find any document in seconds" reads better above "vector-indexed retrieval," though both can appear together for a technical audience.
5. **CTA design** — one primary action per page (not competing CTAs), CTA copy stating the specific next step ("Start a free workspace," not "Learn more"), and CTA placement at natural decision points (end of hero, end of value prop, end of page) rather than only once.

## What NOT to do

- Never fabricate specific numbers, testimonials, customer names, or claims — flag where real content/data is needed and ask, rather than inventing placeholder-that-looks-real copy.
- Don't default to generic SaaS-landing-page boilerplate ("Empower your team to unlock synergies") — tie copy to the platform's actual capabilities as reflected in the codebase and this repo's stated architectural direction.
- Don't optimize copy in isolation from the rendering-strategy decision in `seo-crawlability` — hero copy and meta description often should align, and both need to land in server-delivered HTML if SEO matters for the page.

## Handoff

Once copy and structure are drafted, hand implementation to `frontend-ui-engineering`, visual-token compliance to `design-system-consistency`, and crawlability concerns to `seo-crawlability` — this skill owns what the page says and in what order, not how it's built or styled.
