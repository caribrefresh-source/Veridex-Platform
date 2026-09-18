# D1 — applying the provider firewall: runbook

**Status:** Draft for review. **Nothing has been applied. No `POST` or `PUT`
has been issued.**

Implements the ruleset in `provider-firewall-rules.yml`; rationale and costs in
`provider-firewall.md`. Evidence labels per `.claude/CLAUDE.md` §1.

## 0. Gate — do not start until all five are true

1. `veridex-agent-2` snapshot created and confirmed.
2. Console shell reached on `veridex-server-1` and `veridex-agent-2` through the
   browser, without SSH.
3. Server recovery command proven from that console.
4. Worker recovery path proven from that console (`crictl` → Cilium container →
   `PolicyAuditMode=Enabled`).
5. Evidence recorded; register entry closed.

**Why D1 is gated on the same drill as D2, despite being "cheap to fix":** the
ruleset includes tcp/22. A provider firewall that blocks SSH is only an API call
away from repair *if the API session still works and you can still get in to
diagnose*. Cheap-to-fix is conditional, not inherent.

## 1. What exists today

`VERIFIED` 2026-09-18, read-only:

- **No user firewall policies exist** — `GET /users/253927/firewall-policies`
  returns `[]`. D1 creates the first ones.
- Each server's public interface has netcup's own copied policy attached
  ("netcup Mail block"), with a **per-server** policy id — e.g. `276409` on
  server-1, `277161` on agent-2. These must be preserved on every `PUT`.
- **No failover IPs are owned** — `GET /users/253927/failoverips/v4` returns
  `[]`. Noted because a netcup failover IPv4 is reassignable through this same
  API, which would give real VIP-style ingress failover instead of DNS-paced
  failover. Out of scope for D1; worth its own decision later.

## 2. The one unknown that decides whether D1 works at all

`ServerFirewallSave` accepts only **policy ids** (`copiedPolicies`,
`userPolicies`, `active`). It has **no field for the implicit rule**, yet the
read model returns `ingressImplicitRule` / `egressImplicitRule`.

So how ingress becomes `DROP_ALL` is `UNKNOWN`. The likely behaviour is that
netcup flips the ingress default to drop once a user policy with INGRESS rules
is attached — but that is an assumption, and the whole value of D1 rests on it.

**This is why step 4 reads the firewall back before touching a second node.** If
`ingressImplicitRule` is still `ACCEPT_ALL` after attaching the policy, D1 has
changed nothing: unlisted ports remain reachable, the NodePort bypass is still
open, and the correct response is to stop and rethink — not to continue to the
other four nodes.

## 3. Step 1 — create the two policies (account level)

`POST /api/v1/users/253927/firewall-policies`

Common policy, for every node:

```json
{
  "name": "veridex-public-common",
  "description": "SSH, Traefik NodePorts, ICMP echo. Source of truth: docs/security/provider-firewall-rules.yml",
  "rules": [
    {"direction": "INGRESS", "protocol": "TCP", "action": "ACCEPT", "destinationPorts": "22", "description": "SSH"},
    {"direction": "INGRESS", "protocol": "TCP", "action": "ACCEPT", "destinationPorts": "32537", "description": "Traefik websecure NodePort (Argo CD)"},
    {"direction": "INGRESS", "protocol": "TCP", "action": "ACCEPT", "destinationPorts": "32538", "description": "Traefik grafana-https NodePort"},
    {"direction": "INGRESS", "protocol": "ICMP", "action": "ACCEPT", "description": "echo, so nodes stay diagnosable"}
  ]
}
```

Worker policy, attached only to the two agents:

```json
{
  "name": "veridex-public-worker",
  "description": "Public HTTP/HTTPS on ingress nodes only (plan Rev 3a). Source of truth: docs/security/provider-firewall-rules.yml",
  "rules": [
    {"direction": "INGRESS", "protocol": "TCP", "action": "ACCEPT", "destinationPorts": "80", "description": "HTTP, redirects to HTTPS"},
    {"direction": "INGRESS", "protocol": "TCP", "action": "ACCEPT", "destinationPorts": "443", "description": "HTTPS"}
  ]
}
```

Creating policies attaches nothing. Record both returned ids.

## 4. Step 2 — attach to `veridex-agent-2` first, and stop

`agent-2` is the canary: a worker, not the tunnel endpoint, and the node already
chosen for D2's canary.

1. `GET /servers/939123/interfaces` → the public interface's `mac`.
2. `GET /servers/939123/interfaces/{mac}/firewall` → record the existing
   `copiedPolicies` ids **before** changing anything. This is the rollback
   state.
3. `PUT /servers/939123/interfaces/{mac}/firewall`:

   ```json
   {
     "copiedPolicies": [277161],
     "userPolicies": [<common-id>, <worker-id>],
     "active": true
   }
   ```

4. `GET` it back. **Stop conditions, any one of which ends D1:**
   - `ingressImplicitRule` is not `DROP_ALL` → §2's assumption is wrong.
   - `active` is not `true`.
   - the netcup copied policy is no longer attached.
5. Verify externally, from off-cluster:
   - tcp/22 still completes a TCP handshake on agent-2.
   - 80, 443, 32537, 32538 still answer.
   - a port that is *not* listed — e.g. the 31500 probe from the original
     finding — is now refused where it previously answered. **This is the
     positive proof D1 exists at all**; the other checks only prove nothing
     broke.
6. Leave it for an observation window. Confirm the node stays Ready, Argo CD
   still reconciles, and Hubble shows no new drops.

## 5. Step 3 — the remaining nodes, one at a time

Order, mirroring D2 and for the same reason: `veridex-agent-1`, then
`veridex-server-3`, `veridex-server-2`, and **`veridex-server-1` last** — it
terminates the SSH tunnel that carries `kubectl` from the operator workstation.

Control-plane nodes get `veridex-public-common` **only** — no worker policy, so
80/443 stay closed there, matching the Stage C DaemonSet placement.

Re-verify SSH reachability after each node before starting the next.

## 6. Rollback

Per node, restoring exactly what step 2 recorded:

```json
{ "copiedPolicies": [<recorded id>], "userPolicies": [], "active": true }
```

Then, once no interface references them, `DELETE
/users/253927/firewall-policies/{id}` for both policies.

This rollback runs entirely through the provider API, so it does **not** depend
on SSH, on `kubectl`, or on the node being reachable — which is the property
that makes D1 safer than D2. It does depend on the SCP session, which is why an
authenticated session should be open before starting.

## 7. After D1

- Run `scripts/verify-provider-firewall.py`; expect exit 0.
- Record evidence under `docs/evidence/gap-closure/tls-public/stage-d1/`,
  including the before/after firewall reads and the refused-port proof.
- Update `docs/security/nodeport-bypasses-host-firewall.md`: if step 4.5's
  negative test passes on every node, that finding is closed by D1 rather than
  by D2.
- Only then start D2 (the Cilium host policy), whose public-port rules now sit
  behind a gate that has been proven to work.
