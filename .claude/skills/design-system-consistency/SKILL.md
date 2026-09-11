---
name: design-system-consistency
description: "Use whenever building or reviewing any page or component in apps/frontend (admin-rbac, files, home, review, signin, tenant-admin, or new marketing/landing pages) — checks that colors, typography, spacing, and components match the shared Veridex brand tokens in apps/frontend/src/shared/brand.css instead of drifting into one-off hex codes, ad-hoc font choices, or duplicate component patterns. Trigger this proactively whenever new UI is added or a new page bundle is created, even if the user doesn't explicitly ask about design consistency or a 'design system'."
---

# Design System Consistency

`apps/frontend` is a multi-bundle Vite app (`src/bundles/admin-rbac`, `files`, `home`, `review`, `signin`, `tenant-admin`, each with its own `index.css`), sharing one token source: `apps/frontend/src/shared/brand.css` (Tailwind v4 `@theme`, "Veridex Brand Strategy"). Because each bundle is built somewhat independently, and marketing/landing pages will add yet more bundles, visual drift across pages is the actual risk this skill exists to catch — not abstract "design quality."

## What to check

1. **Color** — every color in new markup should resolve to a `--color-brand-*` token (`primary`, `secondary`, `accent`, `verification`, `success`, `bg`, `danger`, `danger-bg`, `surface`, `border`, `muted`, `neutral`, `neutral-text`) via Tailwind utility classes, not raw hex values or arbitrary Tailwind grays/blues. If a needed color genuinely isn't covered by an existing token, that's a signal to add a token to `brand.css` — not to hardcode one page's hex value.
2. **Typography** — headings use `--font-heading` (Geist), body text `--font-body` (Source Sans 3), monospace/code `--font-mono` (JetBrains Mono), tabular/data display `--font-data` (IBM Plex Sans). Check that new pages aren't silently falling back to system fonts because a bundle's `index.css` doesn't import `shared/brand.css`.
3. **Spacing & scale** — prefer Tailwind's default scale over arbitrary pixel values (`p-[13px]` is a drift smell); check new pages roughly match the density/rhythm of existing bundles rather than inventing a new scale for marketing pages.
4. **Component reuse vs. duplication** — before a new bundle re-implements a button, modal, dropdown, or form field, check whether an equivalent already exists via the shared Radix-based primitives used elsewhere (`@radix-ui/react-dialog`, `-dropdown-menu`, `-popover`, `-tooltip`, `-context-menu`). New marketing pages copying a hand-rolled variant of something that already exists in an app bundle is the highest-value thing to catch.
5. **Focus/interaction states** — the shared `.focus-ring` utility (see `brand.css`) should be the only focus treatment in use; a page defining its own `:focus` outline is a drift signal, not a stylistic choice.

## How to check it

Read `apps/frontend/src/shared/brand.css` first to get the current token set (don't assume it matches what's summarized here — it's the source of truth and may have changed). Then grep the bundle(s) under review for raw hex codes (`#[0-9a-fA-F]{3,6}`), arbitrary Tailwind values (`\[.*px\]`), and font-family declarations outside `brand.css`, and flag each with the token it should be using instead.

## Marketing pages specifically

New landing/marketing pages should extend the existing token set, not fork a separate visual identity — the brand needs to feel the same whether someone lands on the marketing site or the authenticated app. If marketing design requirements genuinely need something the current token set can't express (e.g. a hero-section treatment), extend `brand.css` deliberately and note it, rather than letting the marketing bundle quietly diverge.
