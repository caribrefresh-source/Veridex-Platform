# front-end-design

Design and implement frontend UI components, layouts, and styles.

## Workflow

1. **Understand the goal** — What page, component, or interaction is being built? Who is the user?
2. **Audit existing styles** — Check for existing CSS frameworks, design tokens, component libraries, or style guides in the project before writing new styles.
3. **Design first** — For non-trivial UI, describe the layout and component hierarchy before writing code. Confirm with user before implementing.
4. **Implement** — Write clean, semantic HTML/JSX, scoped CSS or Tailwind classes, and accessible markup (ARIA labels, keyboard nav, contrast ratios).
5. **Responsive** — Mobile-first. Test at 375px, 768px, and 1280px breakpoints.
6. **Preview** — Start the dev server and use the browser (via Playwright MCP or chrome MCP) to screenshot the result before reporting done.

## Standards

- Semantic HTML: use `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>` correctly
- Accessibility: WCAG 2.1 AA minimum — contrast ratio ≥ 4.5:1, all interactive elements keyboard-focusable
- No inline styles unless dynamically computed
- CSS custom properties (variables) for colors, spacing, and typography
- Component isolation: styles scoped to component, no global side effects

## Common Tasks

**New component**: Identify props/state, write markup, add styles, export, add to parent.

**Layout fix**: Inspect current layout, identify flex/grid issues, fix without changing unrelated styles.

**Responsive fix**: Add/adjust media queries, test at all breakpoints.

**Dark mode**: Use `prefers-color-scheme` media query or CSS class toggle. Map all colors to variables first.

**Animation**: CSS transitions preferred over JS animations. `prefers-reduced-motion` must be respected.

## Framework Detection

Check project for framework before starting:
```
ls package.json && cat package.json | python3 -m json.tool | grep -E '"react|"vue|"svelte|"next|"nuxt|"astro|"tailwind'
```

## Output

Produce working code. Then screenshot via Playwright to confirm visual result. Report: what was built, what breakpoints tested, any accessibility notes.
