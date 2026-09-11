---
name: accessibility-audit
description: "Use whenever building, reviewing, or shipping any page in apps/frontend (admin-rbac, files, home, review, signin, tenant-admin, or new marketing/landing pages) — audit for WCAG 2.1/2.2 AA compliance: color contrast, ARIA roles, keyboard navigation, focus order, and screen-reader flow. Trigger this proactively any time new interactive UI, forms, modals, or navigation are added, not just when the user explicitly says 'accessibility' or 'a11y'."
---

# Accessibility Audit

Audits pages in `apps/frontend` (React 19 + Radix UI primitives + Tailwind v4) against WCAG 2.1/2.2 AA. Radix gives correct ARIA semantics out of the box for its primitives (`@radix-ui/react-dialog`, `-dropdown-menu`, `-tooltip`, `-popover`, `-context-menu`, `-scroll-area`) — most real violations come from custom markup built *around* those primitives, not the primitives themselves.

## What to check, in order

1. **Contrast** — check custom text/background pairs against `apps/frontend/src/shared/brand.css` token values (`--color-brand-primary` #0f172a, `--color-brand-secondary` #475569, `--color-brand-muted` #94a3b8, `--color-brand-accent` #2563eb, etc.). Muted/secondary tokens on `--color-brand-bg` (#f8fafc) are the most likely to fail 4.5:1 for body text — verify, don't assume.
2. **Focus visibility** — every interactive element must carry the shared `.focus-ring` class (defined once in `brand.css`, tagged for WCAG 2.4.7). If a new custom button/link/control skips it, that's a defect, not a style choice — the codebase intentionally centralized this so there'd be exactly one focus rule to audit.
3. **Keyboard navigation** — tab order matches visual order, no keyboard traps, `Escape` closes Radix overlays (should be automatic — verify it wasn't broken by custom event handling), all mouse-only interactions (drag targets via `@dnd-kit`, custom dropdowns) have a keyboard equivalent.
4. **ARIA correctness** — for hand-rolled markup (not Radix primitives), verify roles/labels are accurate, not decorative. A `<div onClick>` styled as a button needs `role="button"`, `tabIndex=0`, and Enter/Space handling, or should just be a `<button>`.
5. **Screen-reader flow** — form fields have associated `<label>`s or `aria-label`, error messages from `react-hook-form` + `zod` are announced (`aria-live` or `aria-describedby`), decorative icons (`lucide-react`) get `aria-hidden="true"`, meaningful icons get accessible names.

## How to verify, not just review

Static reading catches maybe half of these. Use `browser-testing-with-devtools` (Chrome DevTools MCP) against the running app (`npm run dev` in `apps/frontend`) to actually inspect the accessibility tree, computed contrast, and focus order — don't rely on source inspection alone for contrast or tab-order claims.

For durable regression coverage, `@axe-core/playwright` is the standard automated-a11y-testing pairing with the Playwright setup already in `apps/frontend/playwright.config.ts` — propose adding it as a devDependency and a scan in `apps/frontend/e2e` rather than a one-off manual pass, but this is a suggestion to make to the user, not something to install unprompted.

## Output format

Report findings as: element/file, WCAG success criterion violated, severity, and the concrete fix (not just "improve contrast" — give the token or value to use).
