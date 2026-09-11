---
name: visual-regression-testing
description: "Use whenever adding or modifying UI in apps/frontend and the change should be protected against visual regressions — sets up or extends Playwright screenshot-diff tests (toHaveScreenshot) across breakpoints, layered on the existing Playwright e2e setup in apps/frontend/playwright.config.ts and apps/frontend/e2e. Trigger this proactively after any styling, layout, or component change, and especially when building new marketing/landing pages, not only when the user explicitly says 'visual regression' or 'screenshot testing'."
---

# Visual Regression Testing

`apps/frontend` already has `@playwright/test` as a devDependency and an `e2e/` directory (`playwright.config.ts`) covering functional behavior. Playwright's built-in `expect(page).toHaveScreenshot()` does pixel-diff screenshot testing natively — no new package is needed for this, only new test files and baseline images.

## What this catches that the existing e2e tests don't

The current Playwright suite (and Vitest component tests) verify *behavior* — a button click does the right thing, a form submits. They don't catch a spacing token drifting, a font failing to load, a card losing its shadow, or a marketing page's hero section shifting layout on a mid-size viewport. That's what screenshot diffing is for.

## How to set it up

1. **Reuse `playwright.config.ts`** — check its existing `projects`/`viewport` config before adding new ones; extend breakpoints there rather than hardcoding viewport sizes inside individual test files.
2. **Cover real breakpoints**, not just desktop: mobile (~375px), tablet (~768px), and desktop (~1280px+) at minimum — check what the existing config already defines before assuming these numbers.
3. **One spec per bundle/page** under `apps/frontend/e2e`, following whatever naming convention the existing e2e tests use — don't introduce a parallel test-organization scheme.
4. **Stabilize before snapshotting**: disable animations (Playwright's `toHaveScreenshot` supports this via config), wait for fonts to load (the app pulls in `@fontsource/*` packages — a font-swap mid-screenshot is a common source of flaky diffs), and mask genuinely dynamic content (timestamps, live data from TanStack Query) rather than trying to make it deterministic.
5. **Baseline images live in git** alongside the spec (Playwright's default `-snapshots` convention) — flag this to the user since it adds binary files to the repo; don't commit baselines without saying so.

## When to run it

Propose running this after any PR that touches CSS, layout, or shared components (including `brand.css` token changes, which by definition affect every bundle) — a single token edit is exactly the kind of change that's easy to verify functionally but silently breaks visually everywhere at once.

## What NOT to do

Don't hand-roll a custom screenshot-diffing script — Playwright's native capability already does this and is already installed; adding a separate tool (e.g. Percy, Chromatic) would be new infrastructure for something already covered, and isn't justified unless the user specifically wants cloud-hosted diff review across a team.
