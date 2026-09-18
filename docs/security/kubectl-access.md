# kubectl access — daily identity and break-glass

Two credentials, deliberately kept apart. Evidence labels per
`.claude/CLAUDE.md` §1.

| | Daily | Break-glass |
|---|---|---|
| Identity | ServiceAccount `veridex-access/veridex-operator` | k3s built-in `system:admin` certificate |
| Rights | **Read-only** (`veridex-operator-read`): get/list/watch, **no Secrets, no exec** | Full cluster-admin (`system:masters`) |
| Revocable | **Yes** — delete the token Secret | **No** — only by rotating k3s's certificates |
| Kubeconfig | `~/.kube/config`, context `veridex-netcup` | `~/.kube/veridex-netcup-breakglass.yaml` only |
| Use for | looking at the cluster | exec, emergency mutations, anything read-only cannot do |

## Why

Until 2026-09-18 the default kubeconfig authenticated as `system:admin`: a
standing cluster-admin credential that cannot be revoked.
`.claude/CLAUDE.md` §8 says cluster-admin has no standing legitimate use
outside a recorded, expiring emergency mutation. The certificate is kept —
there is no other way to recover the cluster — but it is no longer what an
ordinary `kubectl` reaches.

Keeping it in a **separate file**, not a second context in the same file, is
the point: `kubectl config use-context` cannot reach it by accident, and every
break-glass command has to name `--kubeconfig` explicitly, which also makes it
easy to record.

## Daily use

Nothing changes. `kubectl get pods -A`, logs, Argo CD Applications, Cilium
policies, events — all readable. `scripts/start-netcup-kube-tunnel.ps1` still
works: its identity check only reads the `kube-system` namespace.

Secrets are not readable, and that is intended: read access to Secrets would
expose ServiceAccount tokens and repository credentials, which would make this
identity admin-equivalent in practice.

## Break-glass use

```powershell
kubectl --kubeconfig $HOME\.kube\veridex-netcup-breakglass.yaml <command>
```

Record each use per `.claude/CLAUDE.md` §4 — who, why, what changed.

## Rotating or revoking the daily token

```powershell
kubectl --kubeconfig $HOME\.kube\veridex-netcup-breakglass.yaml `
  -n veridex-access delete secret veridex-operator-token
```

The old token stops working at once. The Secret is Git-managed, so Argo CD's
`selfHeal` recreates it within a sync interval with a **new** token. Copy the
new value into `~/.kube/config` as the `veridex-operator` user's `token`.

Deleting the Secret is therefore both "revoke" (if the token leaked) and
"rotate" (on a schedule). To revoke permanently, remove the binding in
`kubernetes/cluster/access/operator.yaml` through a reviewed change.

## When a new CRD appears

`veridex-operator-read` lists every non-core API group explicitly. A CRD added
in a new group is **not** readable until its group is added to that list. That
is deliberate: new access comes from a reviewed change, not silently.

## Out of scope

- **The old K3s-HA cluster** is a separate context, <!-- provider-drift-ok: documents the read-only reference context separation -->
  `k3s-ha-READONLY-reference`. It is a read-only reference and never a change <!-- provider-drift-ok: documents the read-only reference context separation -->
  target. It was renamed from `default` on 2026-09-18 so no tool that picks
  "the default context" can reach it.
- **Short-lived tokens.** Minting them needs `create` on
  `serviceaccounts/token`, which this identity lacks, so every session would
  start by using break-glass. Worth revisiting if an identity provider (OIDC)
  is ever added.
