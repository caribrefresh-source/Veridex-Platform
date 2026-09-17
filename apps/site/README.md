# Veridex public site

This is the isolated static marketing-site entry point required by Stage B of
the public-TLS gap-closure plan. It intentionally contains only `/`, `/plans`,
and branded not-found behavior. It does not import or bundle the platform
frontend, its protected routes, authentication, or administration features.

## Local verification

```text
npm ci
npm run lint
npm run typecheck
npm test
npm run build
docker build -t veridex-site:local .
```

The runtime image serves compiled assets as an unprivileged user on port 8080.
`/healthz` is the intended readiness and liveness endpoint. Production must use
an immutable registry digest; a tag-only deployment does not satisfy EG91.
