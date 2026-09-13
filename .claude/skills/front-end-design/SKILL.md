---
name: front-end-design
description: "Use whenever designing or implementing UI components, layouts, or styles in apps/frontend — the React 19 + Vite 6 + Tailwind v4 + Radix UI codebase serving the home, signin, admin-rbac, files, share, tenant-admin, and review pages. Project-scoped version of the generic front-end-design skill, tailored to this repo's real bundle structure, brand tokens, and API-client pattern. Trigger proactively for any new component, page, or layout/style change in apps/frontend, not only when the user says 'design' explicitly."
---

# Front-End Design (apps/frontend)

Project-scoped version of the generic `front-end-design` skill, grounded in this repo's actual stack instead of generic web-dev defaults. Companion skills own adjacent concerns — hand off rather than duplicate: `accessibility-audit` (deep WCAG pass), `design-system-consistency` (token-drift check across bundles), `visual-regression-testing` (Playwright screenshot diffing), `seo-crawlability` and `landing-page-copy` (public marketing pages only).

## The stack (skip framework detection — this is already known)

React 19, Vite 6, Tailwind v4, TypeScript, Radix UI primitives (`@radix-ui/react-dialog`, `-dropdown-menu`, `-popover`, `-tooltip`, `-context-menu`, `-scroll-area`), TanStack Query for server state, `react-hook-form` + `zod` for forms, `zustand` for client state, `lucide-react` for icons, `@dnd-kit` for drag-and-drop. Don't run generic framework-detection commands — this is it.

## Where code goes

- `apps/frontend/src/bundles/<name>/` — one per Vite entry (`admin-rbac`, `files`, `home`, `review`, `signin`, `tenant-admin`; `share` too). Each has its own `index.css`. New pages register here **and** as a new `rollupOptions.input` entry + `restructure-dist` mapping in [vite.config.ts](apps/frontend/vite.config.ts) if it's a genuinely new top-level page.
- `apps/frontend/src/domains/<domain>/` — domain-owned pages/components (e.g. `domains/documents/pages/FileManagerPage.tsx`, `domains/documents/components/ShareDialog.tsx`). This is the target domain-driven structure per the v8 frontend architecture spec — prefer extending an existing domain folder over adding loose components to a bundle when the component is domain logic (documents, sharing, tags, notifications), not bundle-shell chrome.
- `apps/frontend/src/shared/` — cross-domain only: `brand.css` (design tokens), `api/gatewayClient.ts` + `api/endpoints/*.ts` (typed API client), `types/`. Cross-bundle imports should go through here, not directly between bundles.

## Workflow

1. **Understand the goal** — which page/bundle, which domain, which user role (RBAC bundles differ from the public marketing home page).
2. **Audit existing styles first** — read `apps/frontend/src/shared/brand.css` for the actual current token set before writing any color, font, or spacing value. Don't assume the tokens listed below haven't changed since this skill was written.
3. **Design first** — for non-trivial UI, describe layout and component hierarchy before writing code; confirm with the user before implementing, same as always.
4. **Implement**:
   - Reach for an existing Radix primitive before hand-rolling a dialog/dropdown/tooltip/popover — this codebase already has them wired for accessibility.
   - Colors/fonts/spacing come from `brand.css` tokens (`--color-brand-*`, `--font-*`) via Tailwind utility classes — no raw hex codes, no arbitrary pixel values, no CSS custom properties invented ad hoc when a token already covers the case.
   - Data fetching goes through the typed client in `src/shared/api/` (`gatewayClient.ts` + `endpoints/*.ts`), not raw `fetch`/`axios` in components — this repo's target architecture explicitly forbids untyped fetch calls in UI (Tranche 4 enforcement, `codegen:check` script already exists for the generated OpenAPI clients).
   - Every interactive element gets the shared `.focus-ring` class — it's the one centralized focus-visibility rule in this codebase (WCAG 2.4.7), don't add a competing one.
5. **Responsive** — mobile-first, test at 375px / 768px / 1280px (same breakpoints `visual-regression-testing` uses — keep them aligned so manual checks and automated diffs agree).
6. **Preview** — `npm run dev` in `apps/frontend` (port 5173 per `vite.config.ts`), then screenshot via the browser tools before reporting done. For authenticated bundles (admin-rbac, files, tenant-admin, review), note that a real dev preview needs a signed-in session — check what the existing e2e setup does for auth fixtures rather than improvising a bypass.

## Standards

- Semantic HTML (`<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`).
- WCAG 2.1/2.2 AA minimum — contrast ≥ 4.5:1 against the actual `brand.css` background tokens (not assumed values), all interactive elements keyboard-focusable via `.focus-ring`. For a full audit pass, hand off to `accessibility-audit` rather than duplicating its checklist here.
- No inline styles unless a value is genuinely dynamic (computed position, drag offset, etc.).
- Tailwind utility classes bound to `brand.css` tokens — not raw CSS custom properties invented per-component.
- Component isolation: bundle-level `index.css` for bundle-shell styles only; shared/reusable styling belongs in `brand.css` or a shared component, not copy-pasted across bundles (that's exactly the drift `design-system-consistency` checks for).
- `prefers-reduced-motion` respected for any animation; CSS transitions preferred over JS animation libraries — none are currently installed, and adding one (Framer Motion, etc.) is a dependency decision to flag, not default to.

## Marketing/landing pages (home bundle and beyond)

The `home` bundle is currently the only public marketing page (`entrepeai.com/`, the separate company site outside the Veridex netcup platform), and it's CSR-only today — no SSR/prerendering. Building new landing pages under it inherits that limitation; if SEO matters for the page being built, flag the rendering-strategy question (see `seo-crawlability`) before investing in on-page meta/structured-data work that a crawler may never see. Copy and page structure decisions belong to `landing-page-copy`, not this skill.

## Output

Produce working code, screenshot via the browser tools to confirm the visual result at all three breakpoints, and report: what was built, which bundle/domain it lives in, which tokens/primitives were reused vs. newly added, and any accessibility notes worth a follow-up `accessibility-audit` pass.
