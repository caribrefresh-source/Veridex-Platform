# Argo CD omitempty zero-value gotchas

**Status:** Living reference document. Add an entry every time this bug class recurs; do not delete resolved entries — they are what makes the next one recognizable in under an hour instead of a day.

## The bug class

Some fields in the Argo CD `Application` CRD are `omitempty` in the underlying Go/protobuf type. When you set such a field to its zero value (`false`, `0`, `""`, empty list) in a manifest, the API server accepts it but does not persist it as a distinct value — `omitempty` means "zero value looks the same as absent," so the stored object simply omits the key. Git then has the key; the live object does not. Argo CD's diff engine sees that mismatch as real drift and reports it as `OutOfSync`. Because the live object can never be made to match Git's literal YAML (the API server will strip the key again on every apply), this `OutOfSync` state does not resolve on retry, on `selfHeal`, or on a manual sync — it is permanent until the offending line is removed from Git.

The dangerous part: this doesn't just make one Application look degraded. If the affected Application is itself a parent in an app-of-apps chain, the parent can get stuck refusing to apply *anything new* underneath it — a real Application's sync failure blocking unrelated future work, for a reason that has nothing to do with that future work.

**Rule:** never declare a field's zero-value explicitly if that field is `omitempty` in the CRD. If a field defaults to `false`/`0`/empty, express "use the default" by omitting the field entirely, not by writing the default value out.

## Confirmed instances

### 1. `spec.syncPolicy.automated.prune: false`

- **Where:** K3s-HA repo, `gitops/infra-app.yaml` (parent) vs. `gitops/infra/velero/velero-resources-app.yaml` (child, explicitly declared `prune: false`).
- **Symptom:** `infra` Application stuck `OutOfSync`/`Degraded` on `Application/velero-resources` continuously since 2026-06-24.
- **Fix applied:** added `ignoreDifferences` on the parent excluding `.spec.syncPolicy.automated` (via `jqPathExpressions`) for `group: argoproj.io, kind: Application` — keeps the child's explicit `prune: false` legible in Git while stopping the parent from fighting a field the API server won't persist.
- **Root cause confirmed:** `prune` defaults to `false`; declaring it explicitly is the zero value under `omitempty`.

### 2. `spec.source.directory.recurse: false`

- **Where:** this repo, `gitops/infrastructure/traefik.yaml` and `gitops/infrastructure/monitoring.yaml`.
- **Symptom:** the `root` app-of-apps sat permanently `OutOfSync`, which blocked it from applying the Gate 11 monitoring Application at all — a live incident discovered while standing up baseline observability.
- **Fix applied:** removed the `directory: {recurse: false}` stanza entirely (2026-09-15). `recurse` defaults to `false`, so omitting it is functionally identical and doesn't create the diff.
- **Root cause confirmed:** same mechanism as #1 — `recurse: false` is the zero value under `omitempty`.

## Watch list — plausible next occurrences, not yet confirmed

These are other `Application` spec fields that default to a zero value and are worth a second look if an Application ever shows an unresolvable `OutOfSync` with no other explanation:

- `syncPolicy.automated.selfHeal: false` (default is `false` — only a problem if something explicitly writes `false` rather than omitting it)
- `syncPolicy.automated.allowEmpty: false`
- `retry.limit: 0`
- `syncPolicy.syncOptions` entries that assert a `=false` flag rather than simply not listing the option (e.g. an explicit `CreateNamespace=false`, which K3s-HA's `bootstrap/secrets-app.yaml` currently declares — not yet confirmed as a live problem, but the same shape as both confirmed instances above and worth checking if that Application ever shows unexplained drift)

## Review checklist addition

Before merging any new or edited `Application`/`AppProject` manifest: grep the diff for `: false`, `: 0`, or `: ""` on any field under `spec.syncPolicy` or `spec.source.directory`. If found, ask whether omitting the field entirely would mean the same thing — if yes, omit it instead of writing it out.
