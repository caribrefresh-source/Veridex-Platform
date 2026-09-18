# Stage D — host policy in audit mode: procedure

**Status:** In progress. Steps 1 and 3 are done; the policy is not yet applied.
**Deliverables:** D98 (`kubernetes/cluster/policies/host-policy.yaml`), D99 (this file), D100
(evidence, produced by running it), D101 (rollback drill result).

Evidence labels per `.claude/CLAUDE.md` §1.

## 0. What makes this different from every other stage

`VERIFIED` 2026-09-17, live:

- `enable-host-firewall: true` cluster-wide, and **zero**
  `CiliumClusterwideNetworkPolicy` objects exist. Host endpoints show
  `POLICY (ingress) ENFORCEMENT: Disabled`. So the capability is on and nothing
  is filtered — applying the first policy is what starts enforcement.
- Cilium is v1.20.1, WireGuard on 51871, VXLAN tunnel mode.

`DOCUMENTED` (Cilium host-firewall docs, v1.20):

- Audit mode is **per host endpoint**, set imperatively with
  `cilium-dbg endpoint config <id> PolicyAuditMode=Enabled`.
- **It does not persist across a `cilium-agent` restart.** After a restart the
  node enforces whatever policies exist, immediately.

Two consequences the plan's own text should be read against:

1. Audit mode cannot be expressed in Git. It is an imperative pre-step on each
   node, which under CLAUDE.md §4 is an emergency-style mutation: record who,
   why, and when it is reverted.
2. The audit window is **fragile**. Any event that restarts a Cilium agent —
   a node reboot, an OOM kill, an eviction — ends audit mode on that node and
   begins enforcement. Keep the window short and attended. Do not start it
   before a weekend.

## 1. Prerequisite: the Argo project must permit the resource

`gitops/projects/veridex.yaml` did **not** list `CiliumClusterwideNetworkPolicy`
in `clusterResourceWhitelist`, so Argo CD would have refused to sync it — the
same failure PR #54 and PR #57 fixed for webhook and admission-policy kinds.

**Done:** added in PR #64, merged 2026-09-17 as `94e603a`. Permitting the kind
created nothing.

## 2. Order of operations

Each step has a stop condition. If one is not met, stop — do not continue to
the next.

1. ✅ **Merge the project allow-list change.** PR #64, `94e603a`.
   `cluster-policies` stayed Synced/Healthy.
2. ⬜ **Open a second SSH session to each node and leave it open.** An
   established connection survives a policy that blocks new ones. This is the
   difference between a fixable mistake and a rebuild. **Operator-held — this
   is the one step no automation can do, because it is the escape hatch from
   automation.**
3. ✅ **Enable audit mode on all five host endpoints**, before any policy
   exists. Done 2026-09-17T20:15Z, re-verified 20:23Z; no agent has restarted
   since (all started ~09:59Z). Host firewall is active on `eth0` and `eth1` on
   every node.

   ```bash
   for pod in $(kubectl -n kube-system get pods -l k8s-app=cilium -o name); do
     id=$(kubectl -n kube-system exec $pod -c cilium-agent -- \
       cilium-dbg endpoint get -l reserved:host -o 'jsonpath={$[0].id}')
     kubectl -n kube-system exec $pod -c cilium-agent -- \
       cilium-dbg endpoint config $id PolicyAuditMode=Enabled
   done
   ```

   **Stop condition (EG101):** all five report `PolicyAuditMode: Enabled`. If
   even one does not, do not apply the policy — a node still enforcing is a
   lockout on that node.
4. ⬜ **Merge the policy into the synced path** — this PR moves it to
   `kubernetes/cluster/policies/host-policy.yaml`, where `cluster-policies`
   applies it. Nothing is dropped while audit mode holds. Re-verify step 3
   immediately before merging, not hours earlier: the only thing standing
   between this policy and enforcement is a setting that a single agent restart
   silently clears.

   Note the destination. `kubernetes/infrastructure/cilium/` is **not** synced
   by any Application — Cilium is Ansible-owned bootstrap — so a policy left
   there would never be applied, and the silence would look like success.
5. **Observe.** See §3.
6. **Rollback drill (EG104), while still in audit mode:** delete the policy,
   confirm the host endpoints return to `ENFORCEMENT: Disabled`, re-apply it.
   Proving the escape hatch works **before** it is needed is the point.
7. Leave audit mode on. Enforcement is Stage E, node by node, with SSH verified
   between each.

## 3. What to observe, and for how long

The window must include **an Ansible run and an Argo CD sync**, so node-to-node
and control-plane flows are exercised rather than assumed.

Audit verdicts come from Hubble, filtered to the host endpoint:

```bash
kubectl -n kube-system exec ds/cilium -c cilium-agent -- \
  cilium-dbg monitor --type policy-verdict | grep -i audit
```

**Stop condition (EG102):** zero would-be drops for SSH, the API, etcd, kubelet,
VXLAN, WireGuard, Cilium health, and 80/443/32537/32538. Any audit verdict
against those means the policy is wrong — fix the policy, do not proceed.

Also confirm during the window (EG103): all five nodes Ready, every Argo CD
Application Synced/Healthy, and the external endpoints still answering —
80/443 on both workers, 32537/32538 on all five.

## 4. Rollback

Delete both policies:

```bash
kubectl delete ciliumclusterwidenetworkpolicy veridex-host-baseline veridex-host-public-ingress
```

Host endpoints return to default-allow immediately; policies are dynamic and no
restart is involved. Because the file lives under an auto-synced, self-healing
Argo CD path once it is moved there, a `kubectl delete` alone will be
**reverted by self-heal** — revert the Git commit as well, or the escape hatch
closes behind you within a sync interval. That interaction is the most likely
way this goes wrong in an emergency, which is why step 6 rehearses it.

## 5. Known gaps

- **Ingress only.** Egress is deliberately excluded; see the header of
  `kubernetes/cluster/policies/host-policy.yaml`. D98's wording lists egress, so either the plan
  is amended or a second policy and a second audit window are scheduled.
- **SSH is allowed from the whole internet**, matching today's nftables model
  (rate-limited, key-only). Narrowing it to known addresses would be a real
  improvement and a real lockout risk on a dynamic address; it is a separate
  decision, not a silent change here.
- **Not yet verified live:** that these rules are sufficient. That is precisely
  what the audit window establishes, and why no claim of correctness is made
  before it runs.
