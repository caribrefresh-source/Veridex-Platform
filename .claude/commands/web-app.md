# web-app

Build, run, debug, and deploy web applications end-to-end.

## Workflow

1. **Clarify scope** — New app or feature? What stack? What does "done" look like?
2. **Scaffold** — Generate project structure if new. Follow existing conventions if extending.
3. **Implement** — Build feature: backend route/handler → data layer → frontend component → integration.
4. **Test** — Run existing test suite. Add tests for new code paths. Use Playwright MCP to test UI flows.
5. **Verify in browser** — Start dev server, screenshot golden paths and edge cases via chrome/Playwright MCP.
6. **Deploy check** — Confirm build passes, environment variables set, no dev-only dependencies in prod bundle.

## Stack Detection

```
cat package.json 2>/dev/null | python3 -m json.tool | grep -E 'next|nuxt|astro|remix|svelte|vite|express|fastify|hono|django|flask|rails'
ls Dockerfile docker-compose.yml pyproject.toml go.mod Cargo.toml 2>/dev/null
```

## Common Tasks

**Add API endpoint**:
- Identify router file → add route → add handler → add validation → add error handling → test with curl or Playwright

**Add page/route**:
- Framework-specific: Next.js = `app/` or `pages/`, Nuxt = `pages/`, SvelteKit = `src/routes/`
- Add layout if needed, wire data fetching, add to nav

**Auth integration**:
- Check existing auth middleware → extend session/JWT → protect route → add UI state

**Database query**:
- Use existing ORM/query builder pattern → add migration if schema changes → seed test data

**Environment config**:
- Add to `.env.example`, document in README, never commit actual values

## Dev Server

```
npm run dev 2>/dev/null || yarn dev 2>/dev/null || pnpm dev 2>/dev/null || python manage.py runserver 2>/dev/null
```

## Build & Deploy

```
npm run build 2>/dev/null
# Check for: TypeScript errors, missing env vars, bundle size warnings
```

For K3s deployment: build image → push to registry → update image tag in gitops/ → ArgoCD syncs.

## Output

Working feature with: implementation, tests passing, browser-verified UI (screenshot), and deploy notes if applicable.
