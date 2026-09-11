---
name: frontend-ui-engineering
description: "Use whenever writing or reviewing component-level React/TypeScript code in apps/frontend — file structure, state management choice, composition patterns, and avoiding generic 'AI aesthetic' UI. Project-scoped version of the generic frontend-ui-engineering skill, tailored to this repo's real domain-boundary rules (ESLint-enforced), typed API-client requirement, and brand tokens. Trigger proactively for any new component, hook, or state-management decision in apps/frontend, not only when the user explicitly asks about UI engineering."
---

# Frontend UI Engineering (apps/frontend)

Project-scoped version of the generic `frontend-ui-engineering` skill. That skill covers *how to design a page* (workflow, preview, breakpoints) — this one covers *how the component code itself should be structured* in this specific codebase, where several of the generic skill's suggestions are already **ESLint-enforced rules**, not just conventions to remember.

## Two rules that are enforced, not optional

Read `apps/frontend/eslint.config.js` before assuming either of these — this summarizes it, but the file is the source of truth and may have changed.

1. **Domain boundaries.** Six domains exist: `documents`, `ai`, `review`, `admin`, `workflow`, `billing`. Inside `src/domains/<domain>/{components,hooks,state,api}/`, importing from another domain's internals (`@/domains/<other>/*`) is an ESLint error. `pages/` and `routes.tsx` are each domain's composition layer and may compose across domains — but only through another domain's public surface, never its internals. Cross-domain communication goes through `src/shared/` (events, shared state), not direct imports.
2. **No untyped `fetch`/`axios`.** Inside `src/domains/**/pages/**` and `src/bundles/**`, calling raw `fetch()` or `axios` is an ESLint error (`no-restricted-syntax`, added Phase 12f D155/EG-135) — the message it throws tells you to use `apiClient`/`gatewayClient` or a generated typed client. `src/shared/api/` (`gatewayClient.ts`, `endpoints/*.ts`) is the one place a raw `fetch` is correct; it's the layer that gets generated from OpenAPI. When adding an API call in a new component, write it as a new function in the relevant `endpoints/*.ts` file (see `collab.ts` for the pattern: typed request/response, one exported function per operation) rather than inlining a fetch call, even a "temporary" one.

## File structure

```
src/domains/<domain>/
  pages/          # composition layer — may reference other domains' public surfaces
  routes.tsx       # composition layer
  components/      # domain-internal, cannot import other domains
  hooks/           # domain-internal
  state/           # domain-internal
  api/             # domain-internal, or use src/shared/api/ for cross-domain calls
src/bundles/<name>/ # Vite entry points (admin-rbac, files, home, review, signin, tenant-admin), each with its own index.css
src/shared/         # brand.css tokens, api/gatewayClient.ts + endpoints/*.ts, types/ — the only sanctioned cross-domain import path
```

Not every domain has code in all five subdirectories yet — `documents` is the most built-out today (see `domains/documents/pages/FileManagerPage.tsx`, `domains/documents/components/ShareDialog.tsx`, `TagsDialog.tsx`, `DashboardPanel.tsx`, `NotificationBell.tsx`). Follow that domain's existing layout when adding to a thinner one rather than inventing a new structure per domain.

## State management

This repo has already made the choice the generic skill presents as a decision tree — don't re-litigate it per component:

```
Local state          → useState
Server state          → TanStack Query (already the standard — see domains/documents for query/mutation patterns)
Global client state    → zustand
Forms                  → react-hook-form + zod (@hookform/resolvers already wired)
```

Optimistic updates via TanStack Query's `onMutate`/`onError` (the generic skill's pattern) apply directly here — e.g. a toggle-favorite or revoke-share action should optimistically update the query cache and roll back on error, matching the mutation functions already in `shared/api/endpoints/collab.ts` (`addFavorite`, `removeFavorite`, `revokeShare`, etc.).

## Composition

Prefer composing the existing Radix primitives (`@radix-ui/react-dialog`, `-dropdown-menu`, `-popover`, `-tooltip`, `-context-menu`, `-scroll-area`) over hand-rolling equivalents — they already handle focus trapping, keyboard nav, and ARIA roles correctly, which is exactly the accessibility work the generic skill's Dialog example (manual `useRef`/`useEffect` focus management) is doing by hand for a case this codebase has already solved.

## Design tokens (replaces generic "semantic tokens" guidance)

Use `--color-brand-*` and `--font-*` tokens from `src/shared/brand.css` via Tailwind utility classes — not `text-primary`/`bg-surface` (those are the generic skill's placeholder names, not this project's actual tokens) and not raw hex values. Read `brand.css` directly before styling; token names have changed before and will again.

## Accessibility, responsiveness, avoiding the "AI aesthetic"

The generic skill's guidance on these holds and is worth re-reading in full (contrast ratios, keyboard nav, ARIA labels, the AI-aesthetic anti-pattern table, meaningful empty/error/loading states). Two repo-specific adjustments:

- **Breakpoints**: test at 375px / 768px / 1280px, not the generic skill's 320/768/1024/1440 — kept aligned with `front-end-design` and `visual-regression-testing` so manual checks and automated screenshot diffs agree.
- **Focus management**: use the shared `.focus-ring` class (see `brand.css`) instead of hand-writing a new focus style per component — it's the one centralized WCAG-2.4.7 rule in this codebase.
- For a full compliance pass rather than in-line review, hand off to `accessibility-audit`.

## Verification

- [ ] No ESLint errors — specifically the domain-boundary and untyped-fetch rules, not just general lint cleanliness
- [ ] Renders without console errors
- [ ] Keyboard-navigable (Tab through it), using `.focus-ring`
- [ ] Responsive at 375 / 768 / 1280
- [ ] Loading, error, and empty states handled (TanStack Query gives you `isLoading`/`isError` for free — use them)
- [ ] Colors/fonts/spacing trace to `brand.css` tokens, not invented values
- [ ] New API calls live in `shared/api/endpoints/*.ts`, not inlined `fetch`
