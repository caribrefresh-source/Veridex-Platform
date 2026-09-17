# Gap Closure Plan — Public TLS and the veridexeai.com cutover

Takes `veridexeai.com` from "a Squarespace marketing site, with the netcup
cluster reachable only on obscure high ports behind a self-signed certificate"
to "the netcup cluster serves the site on 443 under a Let's Encrypt certificate,
and Squarespace is retired."

**Status:** IN PROGRESS. Stage A now includes the apex Route 53 migration and
the cert-manager platform is built; the website, low-port ingress, certificates
and the Cilium host policy are not.

---

## Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-09-16 | HTTP-01 design. Superseded — HTTP-01 is fixed to port 80, which is below this cluster's NodePort range, so it required low-port ingress surgery *before* any certificate could be issued. |
| 2 | 2026-09-16 | Rewritten around **DNS-01** on a delegated subdomain. Decoupled certificate issuance from low-port ingress. Scope was one hostname, `grafana.k8s.veridexeai.com`, keeping Squarespace as the apex. |
| **3** | **2026-09-17** | **This revision.** Scope changed by the repository owner: the website itself moves onto this cluster, the apex points at netcup, and Squarespace is retired. That makes ports 80/443 mandatory rather than deferred, so Revision 2's deliberate deferral of low-port ingress no longer holds. Also folds in the security work (D84–D87) that Revision 2 predates, and the low-port spike that removed its largest `UNKNOWN`. |

Revision 2's central decision — **DNS-01, not HTTP-01** — still stands and still
pays off. Certificate issuance remains independent of inbound ports. Low ports
return only to *serve traffic*, which is a much smaller and better-understood
problem than making ACME validation work.

---

## 0. Plan identity, numbering, and standing

**This is not a numbered gate.** Gate 12 is Longhorn; cert-manager appears in the
Revision 3 plan only inside Gate 32's workload-mapping list. This document
follows the precedent of `Gap Closure Plan — Network Policy.txt`: phased
gap-closure work running alongside the numbered gates.

**Numbering.** Confirmed by the repository owner (R1, answered 2026-09-16): this
plan consumes the gate ledger's cumulative sequence. **Append only, never
renumber** — the ledger's own rule.

| Range | Status |
|---|---|
| D63–D64 | Built (delegated DNS zone) |
| D65–D67 | Allocated, not built (DNS credential + evidence) |
| D68–D72 | **Built** (cert-manager platform) |
| D73–D78 | Allocated, not built (first certificate) — re-scoped in this revision |
| D79–D80 | **Built** (cert-manager metrics + alerts) |
| D81–D83 | Allocated, not built (drift check, prior-drift record, closure) |
| D84–D87 | **Built** (security work — see §3) |
| **D88+** | **New in this revision** |

Exit gates: EG68–EG89 allocated, EG73–EG77 passed. **New work starts at EG90.**

> Revision 2 §8 said "Gate 12 then begins at D84/EG90". That is now wrong —
> D84–D87 were consumed by the security work. Gate 12 begins after this plan's
> last number.

**Evidence labels** (CLAUDE.md §1): `VERIFIED` = observed directly; `DOCUMENTED`
= vendor docs, unconfirmed here; `ASSUMED`/`UNKNOWN` = must be proven.

---

## 1. Current state

### 1.1 Built and verified

| Fact | Evidence | Label |
|---|---|---|
| Route 53 public hosted zone `veridexeai.com` exists; the registrar nameservers were changed from Squarespace to Route 53 | 1.1.1.1 and 8.8.8.8 returned the four Route 53 nameservers on 2026-09-17; the operator workstation's system resolver still returned the prior Squarespace set during propagation | `VERIFIED` |
| Apex website records remain on Squarespace — 4 Squarespace A records and the `www` CNAME were copied into Route 53 | Queried live 2026-09-17; the DNS authority changed but website origin did not | `VERIFIED` |
| Child zone `k8s.veridexeai.com` remains delegated to its original Route 53 hosted zone | Queried live 2026-09-17 | `VERIFIED` |
| No MX records; SPF is `v=spf1 -all` — **email is not used on this domain** | Queried live; confirmed by the owner | `VERIFIED` |
| cert-manager v1.21.2, digest-pinned, GitOps-reconciled, webhook serving | EG73–EG77 all PASS | `VERIFIED` |
| cert-manager issues end-to-end | A self-signed `Certificate` reached `Ready=True` with a real `notAfter`, then was deleted | `VERIFIED` |
| `--enable-certificate-owner-ref` unset → default `false`; deleting a Certificate does **not** delete its Secret | Confirmed live — the probe Secret survived and needed explicit deletion | `VERIFIED` |
| cert-manager scraped; 4 certificate alerts loaded in vmalert, no rule errors | Live query of vmagent/vmalert | `VERIFIED` |
| **Cilium serves `hostPort`** — `HostPort: Enabled` | Agent status, plus a real pod that bound host :80 and served traffic | `VERIFIED` |
| **`NET_BIND_SERVICE` is NOT required** for hostPort 80/443 | Test pod ran `runAsNonRoot: true`, `capabilities: drop [ALL]`, containerPort 8080, hostPort 80 — served fine | `VERIFIED` |
| Nodes have public IPv6 (`2a0a:4cc0:…` on eth0) | Cilium agent status | `VERIFIED` |
| No website exists on this cluster | No `apps/` content on main; no application workloads running | `VERIFIED` |
| The marketing site source is `old-site/frontend` — "EntrepEAI", 11 deps, prebuilt `dist/`, Dockerfiles | Local inspection | `VERIFIED` |
| The application frontend (`dip-frontend`, 7 bundles, own SDK) needs the data plane — Gates 12–16, none built | Local inspection + cluster state | `VERIFIED` |

### 1.2 Security layer state

Closes the bypass found on 2026-09-17
(`docs/security/nodeport-bypasses-host-firewall.md`).

| Layer | State | What it does / doesn't |
|---|---|---|
| **Admission policy** (D85) | **Live, enforcing** | Denies `hostPort` and Service `NodePort`/`LoadBalancer` outside `kube-system`. **Preventive only** — stops new exposure being created; does not filter traffic to anything already exposed. |
| **Cilium host firewall — capability** (D87) | **Enabled, inert** | `Host firewall: Enabled [eth0, eth1]` in the running agent. Filters **nothing**: the host endpoint stays default-allow until a `CiliumClusterwideNetworkPolicy` selects it, and none exists. |
| **Cilium host firewall — policy** | **Pending** (Stages D–E) | The actual network control. Not written. |
| nftables (`roles/firewall`) | Live, but **does not gate Kubernetes service traffic** | Still genuinely enforces for SSH and host-bound listeners. Its comments now say so at the point the false claim was made. |

**The residual gap, stated plainly:** every NodePort in this cluster remains
reachable from the public internet on every node, regardless of the nftables
allowlist. Admission control stops new exposure; it cannot retract existing
exposure. Stages D–E close that.

### 1.3 Corrections carried forward

Recorded rather than quietly dropped, because the reasoning matters more than
the outcome:

1. **"Open port 80 the same way I opened 32538."** Wrong — 32538 is a NodePort,
   80 is below the NodePort range. This forced Revision 1's large Phase 1 and
   ultimately Revision 2.
2. **"Wildcards mean one certificate for everything."** Overstated. Kubernetes
   Secrets are namespaced, so a hostname in another namespace needs its own
   `Certificate` and Secret regardless, and issuing the same wildcard in several
   namespaces creates duplicate certificates against a rate limit.
3. **The namespace would be "plain and unlabeled".** Wrong — the namespace lint
   *requires* `veridex.io/owner` and `veridex.io/purpose`, and `monitoring` sets
   the wave/role precedent.
4. **"Remove the upstream `startupapicheck` Job."** v1.21.2 ships none.
5. **The Argo CD Application would live in a `cert-manager/` subdirectory.** On
   `main`, Applications under `gitops/infrastructure/` are flat files.
6. **The Ansible run that "opened 32538 so Grafana could be reached" was a
   no-op.** Grafana was already reachable. The change is retained — it documents
   intent and becomes load-bearing once the bypass is closed — but its commit
   message overstated what it achieved.
7. **The Cilium role checked `cilium-config` instead of the running agent, and
   never actually rolled the DaemonSet.** `cilium upgrade --set
   hostFirewall.enabled=true` rewrites the ConfigMap but leaves the pod template
   untouched, so nothing rolls and the agents keep running with the feature
   **disabled**. The first authorised run left config and runtime diverged —
   one unrelated pod restart away from silently activating a security feature at
   an unpredictable moment. **The role now restarts the DaemonSet explicitly and
   asserts the running agent's own status, not the ConfigMap.** Any future
   Cilium feature flag must be verified the same way: *runtime, not config.*

---

## 2. Execution sequence

Stage A is done. The ordering constraint that governs everything after it:
**the fallback cannot be dropped before the replacement works.** The cluster has
no website today, so pointing the apex at netcup now would take the live site
dark.

| Stage | What | State |
|---|---|---|
| **A** | Delegated DNS zone under API control | **Done** (zone + delegation). Credential outstanding. |
| **B** | Website ported, rebranded, containerised, deployed | **Next** |
| **C** | Traefik ingress on hostPort **80/443** | After B |
| **D** | Cilium host policy in **audit mode** | After C — needs the final port shape |
| **E** | Host policy switched to **enforce** | After D observes clean |
| **F** | Apex certificate, DNS cutover, Squarespace retired | After C and E |

**Why D and E come after C:** the host policy must permit whatever Traefik ends
up binding. Writing it before the ingress shape is settled means writing it
twice. **Why E is separate from D:** audit mode logs what *would* be dropped
without dropping it, and that observation window is the only thing standing
between a wrong rule and a five-node lockout.

---

## 3. Already built (D63–D87)

Recorded here so the closure record (D83) has a single source.

**Stage A — Route 53 DNS (D63–D64, scope expanded by owner 2026-09-17).** The
original `k8s.veridexeai.com` delegation remains intact. The apex
`veridexeai.com` hosted zone is now also present in Route 53 and the registrar
nameservers have been changed to its four Route 53 nameservers. Existing
Squarespace A/CNAME and email-security records were copied so the authority
change does not yet cut the website over. Public resolvers 1.1.1.1 and 8.8.8.8
returned the Route 53 delegation; the workstation resolver still held the old
Squarespace answer during propagation.
*Outstanding:* D65 (scoped API token), D66 (secret-register entry), D67
(evidence file).

**cert-manager platform (D68–D72, EG73–EG77 all PASS).** v1.21.2, all four
images digest-pinned, CRDs split for sync ordering, `ServerSideApply=true`
(mandatory — the CRDs exceed the 262 144-byte annotation limit). Webhook proven
*serving* by rejecting an invalid Issuer and accepting a valid one.

**Observability (D79–D80).** cert-manager scraped; `certificates` alert group
live. `certmanager_certificate_ready_status` emits one series **per condition
value**, so the obvious `== 0` expression would have fired permanently for every
healthy certificate; `{condition="True"} == 0` is load-bearing.

**Security (D84–D87).** AppProject allowlist extended twice (webhook
configurations for cert-manager; admission policy kinds), the host-exposure
admission policies, and the Cilium host firewall capability. See §1.2.

---

## 4. Stage B — Website ported, rebranded and deployed

**Objective** A Veridex-branded marketing site runs on this cluster, reachable
in-cluster, built reproducibly from source held in this repository.

**Scope**

- *In-Scope:* port `old-site/frontend` into `apps/`; rebrand EntrepEAI → Veridex
  in user-visible content; a pinned container image; Deployment + ClusterIP
  Service + Argo CD Application; namespace declaration.
- *Out-of-Scope:* the `dip-frontend` application (blocked behind Gates 12–16);
  any public exposure (Stage C); any certificate (Stage F); CMS or backend.

**Processes Activated**

- *Site build and release* — owner: container build pipeline + Argo CD — drift
  detection: Argo CD `selfHeal`; image pinned by digest.

**Deliverables**

- **D88.** `apps/site/` — the ported source. **Copied, not moved:** the source
  repository it comes from is read-only reference under the repository owner's
  scope rule, never a change target.
- **D89.** Rebrand: every user-visible occurrence of the old brand name becomes
  Veridex, and the old brand's hostname is removed. Not cosmetic —
  `lint-provider-drift.py` **errors** on that hostname, so an unrebranded port
  fails CI by design. (This plan deliberately avoids spelling either string, for
  exactly the same reason.)
- **D90.** A pinned container image, built reproducibly, digest recorded in the
  manifest exactly as Traefik and cert-manager are.
- **D91.** `kubernetes/cluster/namespaces/site.yaml` — namespace with the
  `veridex.io/owner` and `veridex.io/purpose` annotations the lint requires.
- **D92.** `kubernetes/applications/site/` + `gitops/applications/site.yaml` —
  Deployment, **ClusterIP** Service (never NodePort — the admission policy
  denies it), and the Argo CD Application.

**Technical Detail**

- The image must be digest-pinned. A `:latest` tag would make the deployment
  non-reproducible and is the exact failure mode the repo pins against.
- Service is **ClusterIP**. The admission policy (D85) denies NodePort outside
  `kube-system`, and it is correct to do so — the site reaches the internet
  through Traefik, not by publishing its own port.
- Pod security: `runAsNonRoot`, `readOnlyRootFilesystem`, `drop: [ALL]`,
  matching the Traefik and Grafana manifests. A static-content server needs
  nothing more.

**Exit Gate**

- **EG90.** The site pod is Ready and serves HTTP 200 from a ClusterIP probe —
  Method: `curl` from an in-cluster pod — Result: PASS/FAIL.
- **EG91.** The image runs by **digest**, not tag — Method: inspect the running
  pod spec — Result: PASS/FAIL.
- **EG92.** CI passes, including `lint-provider-drift.py` against its
  pre-existing baseline — Method: the PR's CI run, compared error-for-error with
  `main` rather than against zero — Result: PASS/FAIL.
- **EG93.** **Adversarial:** no old-brand hostname and no reference to the old
  cluster survives in the ported tree — Method: run `lint-provider-drift.py`
  over the tree and require zero new errors versus the `main` baseline —
  Result: PASS/FAIL.
- **EG94.** **Adversarial:** a Service of type NodePort in the site's namespace
  is **denied** by admission — Method: server dry-run — Result: PASS/FAIL.
  *(Proves D85 actually protects the new namespace.)*

**Rollback** Revert D92 (Argo CD prunes the workload), then D88–D91. Nothing is
public at this stage and no data is stored, so there is no data-loss surface and
no user-visible effect — the Squarespace site is still serving the domain.

---

## 5. Stage C — Ingress on ports 80 and 443

**Objective** Traefik answers on **80 and 443** on all five node public IPs, so
the cluster can serve a website at a normal URL.

**Scope**

- *In-Scope:* Traefik `Deployment` → `DaemonSet` with `hostPort` 80 and 443; a
  TLS-terminating entrypoint; an HTTP entrypoint; routing the site.
- *Out-of-Scope:* the certificate itself (Stage F — until then 443 serves
  Traefik's self-signed default); retiring 32537/32538; the host policy
  (Stages D–E).

**Processes Activated**

- *Low-port ingress publication* — owner: GitOps `kubernetes/infrastructure/ingress`
  — drift detection: Argo CD `selfHeal`; Stage D/E policy once written.

**Deliverables**

- **D93.** `kubernetes/infrastructure/ingress/deployment.yaml` — Traefik as a
  `DaemonSet` with `hostPort: 80` and `hostPort: 443`, plus the two new
  entrypoints.
- **D94.** `kubernetes/infrastructure/ingress/service.yaml` — updated for the
  DaemonSet; 32537 and 32538 retained unchanged throughout this stage.
- **D95.** The site's `IngressRoute` on the new TLS entrypoint.
- **D96.** `docs/architecture/low-port-ingress-decision.md` — the spike result
  and the chosen mechanism, written from the real output already captured.
- **D97.** `docs/evidence/gap-closure/tls-public/stage-c/` — per-node
  reachability for all five IPs, before and after.

**Technical Detail**

- **Mechanism: M2, hostPort — decided by spike, not assumption** (§1.1). Cilium
  reports `HostPort: Enabled` and a real pod bound host :80 and served traffic.
  The nftables-DNAT alternative (M1) is moot and the k3s NodePort-range widening
  (M3) stays rejected — it would let any Service claim 80/443 cluster-wide.
- **No `NET_BIND_SERVICE`.** Verified: the container binds 8080 internally and
  the datapath maps host :80. No privileged bind happens inside the container,
  so `drop: [ALL]` and `runAsNonRoot: true` are kept.
- **Port names are capped at 15 characters** (IANA_SVC_NAME). This already broke
  a change in this repo — `grafana-websecure`, 18 characters, PR #52. Check
  every new entrypoint name against 15 **before** committing.
- **The `kind` change needs a cutover, not a push.** `Deployment`→`DaemonSet` is
  not an in-place update: Argo CD prunes one and creates the other in an order
  it does not guarantee, so there is a window with **no Traefik at all**, taking
  Argo CD and Grafana down together. Create the DaemonSet under a different name
  alongside the running Deployment, confirm it serves on all five nodes, then
  remove the Deployment.
- **Traefik must stay in `kube-system`.** It is the namespace the admission
  policy exempts, and that exemption is deliberate: the ingress controller is
  the one thing that should publish.
- **hostPort bypasses nftables.** Opening 80/443 in `roles/firewall` is *not*
  required for this to work and would be theatre if presented as the control.
  The control is Stages D–E.

**Exit Gate**

- **EG95.** Port 80 answers on **each of the five** node public IPs — Method:
  `curl` to all five from outside the cluster; all five must answer — Result:
  PASS/FAIL.
- **EG96.** Same for port 443 — Method: TLS connect to all five — Result:
  PASS/FAIL. *(Reachability only. The certificate is still self-signed until
  Stage F; a passing EG96 must not be read as "TLS is working".)*
- **EG97.** Argo CD on 32537 stays reachable **before, during and after** the
  DaemonSet cutover — Method: HTTPS probe at each of those three points,
  compared against the pre-stage response — Result: PASS/FAIL.
- **EG98.** Grafana on 32538 likewise — Method: same three-point probe —
  Result: PASS/FAIL.
- **EG99.** The site is served through Traefik on 443 on all five IPs — Method:
  request with SNI set to the intended hostname; compare responses — Result:
  PASS/FAIL.
- **EG100.** **IIR:** re-sync of `traefik` produces no diff and no pod churn —
  Method: hard-refresh, compare pod UIDs before and after — Result: PASS/FAIL.

**Rollback** Restore the `Deployment` alongside the `DaemonSet`, confirm it
serves, then remove the DaemonSet — the same cutover order in reverse, never a
bare `git revert` letting Argo CD sequence a `kind` swap unattended. 32537 and
32538 are untouched throughout, so Argo CD and Grafana keep working either way.

---

## 6. Stage D — Cilium host policy, audit mode

**Objective** A host policy exists and is **observed** against real traffic
without dropping anything, so it can be proven correct before it is enforced.

**Scope**

- *In-Scope:* a `CiliumClusterwideNetworkPolicy` selecting the host endpoint;
  policy audit mode; an observation window; the flow evidence.
- *Out-of-Scope:* enforcement (Stage E).

**Processes Activated**

- *Host network policy* — owner: Cilium — drift detection: Argo CD `selfHeal`
  plus the audit log itself during this stage.

**Deliverables**

- **D98.** The candidate `CiliumClusterwideNetworkPolicy`, enumerating every
  flow the host legitimately needs: **tcp/22 SSH**, tcp/6443 API, tcp/2379–2380
  etcd, tcp/10250 kubelet, udp/8472 VXLAN, udp/51871 WireGuard, tcp/4240 Cilium
  health, tcp/80 and tcp/443 (Stage C), 32537/32538 while they remain, plus the
  vLAN `10.2.0.0/16` trusted in full, and egress for DNS, NTP, ACME, the Route 53
  API and Backblaze B2.
- **D99.** The audit-mode procedure and its evidence — what was observed, over
  how long, under what traffic.
- **D100.** `docs/evidence/gap-closure/tls-public/stage-d/` — the policy-verdict
  output showing what *would* have been dropped.
- **D101.** A written rollback drill result: the policy removed and re-added,
  proving the escape hatch works **before** it is ever needed.

**Technical Detail**

> ⚠️ **This is the single highest-consequence change in this plan.** Both the
> operational and the break-glass credentials are SSH keys on the same
> workstation (`docs/security/emergency-access.md`), and there is no documented
> console path. A host policy that drops **tcp/22** locks out all five nodes
> simultaneously, and the only remaining route is reinstalling them.

- **Audit mode first, always.** `cilium endpoint config <host-endpoint-id>
  PolicyAuditMode=Enabled` logs what would be denied without denying it. The
  policy is applied **only** with audit already on.
- **Enable audit on every node before applying the policy**, not after. A policy
  applied while one node is still enforcing is a lockout on that node.
- **Observe under real traffic**, including an Ansible run and an Argo CD sync,
  so node-to-node and control-plane flows are exercised rather than assumed.
- The host endpoint is currently default-allow with the capability enabled
  (D87), so this stage changes nothing until the policy is applied — and even
  then, nothing while audit mode is on.

**Exit Gate**

- **EG101.** Audit mode is confirmed active on **all five** host endpoints
  before the policy is applied — Method: query each agent — Result: PASS/FAIL.
- **EG102.** With the policy applied in audit mode, the policy-verdict log shows
  **zero** would-be drops for SSH, the API, etcd, kubelet, VXLAN, WireGuard and
  ports 80/443/32537/32538 — Method: observe over a window that includes an
  Ansible run and an Argo CD sync — Result: PASS/FAIL.
- **EG103.** Everything still works during audit mode — Method: nodes Ready,
  every Argo CD Application Synced/Healthy, and all external endpoints
  answering, checked after the policy is applied — Result: PASS/FAIL.
- **EG104.** The rollback drill succeeds — Method: delete the policy, confirm
  the host endpoint returns to default-allow, re-apply it, and confirm the
  cluster is unaffected throughout — Result: PASS/FAIL.

**Rollback** Delete the `CiliumClusterwideNetworkPolicy`. The host endpoint
returns to default-allow immediately; policies are dynamic, so no restart is
involved. Audit mode is itself the safety net for this entire stage — nothing is
dropped while it is on.

---

## 7. Stage E — Host policy enforcement

**Objective** The host firewall actually filters, closing the bypass, so
`roles/firewall`'s claim becomes true again.

**Scope**

- *In-Scope:* disabling audit mode, node by node; verification at each step.
- *Out-of-Scope:* any change to the policy content — if a rule needs changing,
  go back to Stage D.

**Deliverables**

- **D102.** The enforcement procedure, node by node with a verification gate
  between each.
- **D103.** `docs/evidence/gap-closure/tls-public/stage-e/` — proof that an
  unlisted port is now actually refused, which is the whole point.
- **D104.** `docs/security/nodeport-bypasses-host-firewall.md` updated: the
  finding moves from "preventive control only" to closed, with the date.

**Technical Detail**

- **One node at a time, verifying SSH between each.** Enforce on node 1, confirm
  SSH and the API still work from outside, then node 2. Four nodes remain
  reachable if node 1 goes wrong — the difference between an incident and a
  rebuild.
- **Keep a second SSH session open** to the node being changed for the duration.
  An already-established connection survives a policy that would block new ones,
  which turns a lockout into a fixable mistake.
- The real test is negative: a port that *should* be blocked must now actually
  be refused. Confirming the good paths still work proves nothing about whether
  the policy does anything.

**Exit Gate**

- **EG105.** After each node, SSH and the API still work from outside — Method:
  test per node, before moving to the next — Result: PASS/FAIL.
- **EG106.** **The bypass is closed:** a NodePort on a port not permitted by the
  host policy is **refused** from the public internet — Method: repeat the exact
  probe from the original finding (a NodePort on 31500) and require a timeout
  where it previously returned 200 — Result: PASS/FAIL.
- **EG107.** Intended public ports still answer on all five nodes — Method:
  probe 80, 443, 32537 and 32538 on each of the five public IPs — Result:
  PASS/FAIL.
- **EG108.** **IIR:** an Ansible run and an Argo CD re-sync both complete
  normally with enforcement on — Method: run `prepare-hosts.yml` (expect
  `changed=0`) and hard-refresh every Application (expect Synced, no diff) —
  Result: PASS/FAIL.

**Rollback** Re-enable audit mode on the affected node, or delete the policy
outright. Both take effect immediately without a restart. If SSH is already lost
on a node, the remaining four still have `kubectl`, and the policy can be
deleted through the API from any of them — which is why enforcement is staged
one node at a time.

---

## 8. Stage F — Apex certificate and cutover (outline)

Deferred in detail until Stages B–C land, because its shape depends on them.
Recorded now so the sequence is not lost:

1. **Completed 2026-09-17:** migrate the whole `veridexeai.com` zone to Route
   53 with website records still pointing at Squarespace. Public resolvers show
   Route 53 authority; allow propagation and re-verify before certificate work.
2. Issue a Let's Encrypt certificate for `veridexeai.com` and `www`, **staging
   first**, using the existing DNS-01 solver.
3. Flip the apex A records to the five netcup IPs. This is the cutover; rollback
   is flipping them back.
4. Retire Squarespace **only after** the cluster has served the site
   successfully.

Email is not a constraint — no MX records, SPF is `-all` (§1.1).

---

## 9. Cumulative index

| Stage | Deliverables | Exit gates |
|---|---|---|
| A — Delegated DNS | D63–D67 (D63–D64 built) | EG68–EG72 |
| cert-manager platform | D68–D72 **built** | EG73–EG77 **passed** |
| First certificate | D73–D78 | EG78–EG84 |
| Observability / drift | D79–D83 (D79–D80 built) | EG85–EG89 |
| Security | D84–D87 **built** | — |
| **B — Website** | **D88–D92** | **EG90–EG94** |
| **C — Ingress 80/443** | **D93–D97** | **EG95–EG100** |
| **D — Host policy, audit** | **D98–D101** | **EG101–EG104** |
| **E — Host policy, enforce** | **D102–D104** | **EG105–EG108** |

New in Revision 3: **D88–D104** (17), **EG90–EG108** (19).

---

## 10. Decisions still open

- **R2 (partial).** Provider and zone settled — Route 53, `k8s.veridexeai.com`,
  delegated and verified. **Outstanding:** the scoped IAM credential (D65), which
  blocks every certificate.
- **R3 — resolved 2026-09-17.** The 36 pre-existing findings were genuine
  historical comparisons to the source platform. Each affected documentation
  line now carries the linter's explicit, reasoned `provider-drift-ok` marker;
  the normal non-strict provider-drift check returns zero errors without
  suppressing future unannotated findings.
- **R5 — Gate 11 drift.** PRs #51/#52 changed Traefik and the firewall after
  Gate 11 closed. Reopen-log entry, or is the D82 drift record sufficient?
- **R6 — new.** Grafana currently allows anonymous Viewer access. Once the
  cluster serves a public website on 443, that becomes considerably more
  discoverable. Set `GF_AUTH_ANONYMOUS_ENABLED=false`, or accept it? The cheap
  moment to decide is before Stage C, not after.

R1 and R4 are answered: numbering consumes the ledger sequence; portless URLs
are no longer deferred — Stage C makes them mandatory.

---

## 11. Residual risks

1. **The bypass is still open until Stage E.** Admission control prevents new
   exposure; existing NodePorts remain internet-reachable regardless of nftables.
2. **Stage D/E can lock out every node.** Both credentials are SSH keys, no
   console path. Audit mode, node-at-a-time enforcement and a held-open SSH
   session are the mitigations; none of them is a recovery path.
3. **Two external dependencies in the certificate path** — Let's Encrypt and the
   Route 53 API. Expiry alerting (D79) is what makes either failure visible
   before it becomes an outage.
4. **A standing DNS credential.** Scoped to one zone, but it does not expire and
   there is no rotation process. Rotation belongs with the wider secrets decision
   behind Gate 22.
5. **Stage C changes Traefik's topology** from one replica to one per node —
   the largest blast radius of any ingress change so far, and it takes Argo CD
   and Grafana with it if the cutover is done carelessly.
6. **A rebuild re-issues certificates** and can hit the duplicate-certificate
   limit if rehearsed repeatedly in one week. Rebuild drills must use staging.
7. **The site is a marketing page, not the platform.** `dip-frontend` still
   needs Gates 12–16. Nothing here shortens that.

---

## 12. Immutability, idempotence, repeatability

| Class | Immutable | Idempotent | Repeatable on a rebuild |
|---|---|---|---|
| Delegation records at Squarespace | No — a web panel | No | **No — manual, but set once and static** |
| Records inside the delegated zone | Yes — API-managed | Yes | Yes |
| DNS API token | Value never in Git | Re-apply converges | Manual re-issue |
| cert-manager platform | Yes — digest-pinned | Yes — Argo CD converges | Yes |
| Site image and manifests | Yes — digest-pinned | Yes | Yes |
| Traefik topology | Yes | Yes — but `kind` changes need the cutover, not a blind re-apply | Yes |
| Cilium host firewall flag | Yes — in the role | Yes — **now keyed off runtime, not config** (§1.3.7) | Yes |
| Host policy | Yes — declarative | Yes — dynamic, no restart | Yes |
| Admission policies | Yes | Yes | Yes |

**Not fully repeatable, stated plainly:** the Squarespace delegation is manual —
a one-time static step, unlike Revision 1 where every record was manual. A
rebuild re-issues certificates, which is correct but rate-limited, so rehearsals
use staging.

**No hand-run command is load-bearing.** Everything lands through Ansible or
Argo CD. `kubectl` is used only to observe, to deliver the DNS token
out-of-band, and to back up a Secret before a destructive rollback.
