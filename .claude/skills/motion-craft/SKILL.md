---
name: motion-craft
description: "Use whenever adding or reviewing animation, transitions, or micro-interactions in apps/frontend (admin-rbac, files, home, review, signin, tenant-admin, or new marketing/landing pages) — applies Emil Kowalski's motion-design principles (purposeful timing, consistent easing, physics-based feel, reduced-motion respect) to this repo's actual Tailwind v4 / Radix UI / sonner stack. Trigger proactively for any hover/press/focus transition, dialog/drawer/toast animation, or page-transition work, not only when the user names 'Emil Kowalski' or 'motion design' explicitly."
---

# Motion Craft (apps/frontend)

Grounds Emil Kowalski's (emilkowal.ski) motion-design philosophy — creator of [Sonner](https://sonner.emilkowal.ski) and [Vaul](https://vaul.emilkowal.ski), author of *Animations on the Web* — in this repo's actual stack, not generic animation advice. Companion skills own adjacent concerns — hand off rather than duplicate: `front-end-design` (component/layout implementation), `design-system-consistency` (token drift), `accessibility-audit` (WCAG pass, including motion-triggered vestibular concerns), `visual-regression-testing` (screenshot diffing across breakpoints).

## Starting point already in the repo

`sonner` (Emil Kowalski's own toast library) is already installed and wired into every bundle's `main.tsx` (`<Toaster position="top-right" richColors />`) — this is the one place his actual code already ships here. Read how it's configured before adding new toast-adjacent UI so you're extending the existing pattern, not inventing a second one.

`front-end-design`'s existing standard: **"CSS transitions preferred over JS animation libraries — none are currently installed, and adding one (Framer Motion, etc.) is a dependency decision to flag, not default to."** This skill does not override that — most of Kowalski's principles below are achievable with CSS alone. Only surface a JS animation library (Motion, the maintained successor to Framer Motion) as an explicit proposal if a specific interaction genuinely can't be done with CSS (e.g. shared-layout/FLIP transitions, spring-based drag). If a drawer/bottom-sheet pattern is needed, Vaul is the natural next addition given `sonner` is already his library — flag it the same way, don't install unasked.

## Core principles, translated into this stack

1. **Purposeful, fast micro-interactions** — hover/press/focus transitions in the 100–200ms range, larger surface transitions (dialogs, drawers, page sections) 200–300ms. Nothing animates "because it can" — every transition should communicate a state change (opened, dismissed, reordered, loading), not decorate.
2. **`transform`/`opacity` only** — never animate `width`, `height`, `top`, `left`, or `margin`. This is a hard performance constraint, not a style preference; it's also already implicit in `front-end-design`'s guidance to avoid layout-triggering properties.
3. **One consistent easing curve, not one per component** — define a small timing/easing scale once and reuse it everywhere a transition exists. Kowalski's own default leans toward a spring-like curve (fast out, gentle settle) rather than linear or basic `ease-in-out`. Add it as CSS custom properties in `apps/frontend/src/shared/brand.css` alongside the existing `--color-brand-*`/`--font-*` tokens (e.g. `--ease-out-snappy`, `--duration-fast`, `--duration-base`) — same token-not-hardcoded-value discipline `design-system-consistency` already enforces for color/type/spacing, just extended to motion.
4. **`prefers-reduced-motion` respected everywhere** — already a stated standard in `front-end-design`; this skill's job is to make sure it's not just stated but actually wrapping every new transition (`@media (prefers-reduced-motion: reduce)` disabling or shortening non-essential animation).
5. **Interruptible, not blocking** — an in-flight transition (e.g. a dialog closing) should be interruptible by a new user action, not force the user to wait it out. Relevant wherever Radix dialogs/dropdowns/popovers are already in use — check their exit-animation handling rather than layering a custom one on top.
6. **Stacking and dismissal feel** — toasts (`sonner`) already model this correctly (stacked, swipe/auto-dismiss, non-blocking). Use it as the reference implementation when building any other dismissable-surface pattern (banners, inline alerts) rather than reinventing the feel.

## Workflow

1. Identify what state change the animation communicates — if you can't name one, don't add the animation.
2. Check `apps/frontend/src/shared/brand.css` for existing timing/easing tokens before inventing a new duration or curve inline.
3. Implement with CSS transitions/`@keyframes` bound to those tokens; reach for Radix's built-in open/close animation hooks (`data-state` attributes) before hand-rolling enter/exit logic.
4. Wrap in `prefers-reduced-motion` handling.
5. If CSS genuinely can't express the interaction, stop and flag the JS-library dependency decision explicitly (Motion vs. Vaul vs. hand-rolled) rather than installing silently — same gate `front-end-design` already sets for any new dependency.
6. Preview via `npm run dev` and confirm the motion reads as intended at real interaction speed (screenshots alone won't show timing/easing — describe or screen-record if precision matters).

## Output

Report which state change each new animation communicates, which token(s) it reused vs. newly added to `brand.css`, confirmation `prefers-reduced-motion` is handled, and whether a JS animation dependency was flagged (and why) rather than added by default.
