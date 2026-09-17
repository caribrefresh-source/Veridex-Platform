# Gap Closure Plan — Public TLS (Let's Encrypt) for Cluster Ingress

Closes the gap between "Grafana is reachable from the internet on a self-signed
certificate" (built ad hoc 2026-09-16, PRs #51/#52) and "cluster services are
reachable over publicly-trusted TLS, issued and renewed automatically,
declaratively, with evidence."

**Status:** IN PROGRESS. **Phase 2 (cert-manager platform) is built** and
awaiting merge; Phases 1, 3 and 4 are not started. Phase 1 is blocked on
decision R2 and on the Squarespace `NS` check (§7 P2).

**Revision 2 (2026-09-16).** Rewritten around **DNS-01** validation on a
delegated subdomain, replacing Revision 1's HTTP-01 design. Revision 1 is
superseded in full; §1.2 records why, because the reasoning matters more than
the outcome.

---

## 0. Plan identity, numbering, and standing

**This is not a numbered gate.** Gate 12 is Longhorn; cert-manager appears in the
Revision 3 plan only inside Gate 32's workload-mapping list, never as a gate of
its own. This document therefore follows the precedent of
`Gap Closure Plan — Network Policy.txt`: phased gap-closure work that runs
alongside the numbered gates rather than inside them.

**Numbering — DECISION REQUIRED (see §8, R1).** This plan numbers deliverables
`D63…` and exit gates `EG68…`, continuing the cumulative sequence the gate ledger
maintains (`docs/evidence/gate-ledger.md` Position: last deliverable **D62**, last
exit-gate check **EG67**, Gate 11 closed 2026-09-16 — `VERIFIED`, read from
`origin/main`). Consequence: Gate 12 starts after this plan's last number, and
the ledger Position line must be updated when this plan completes. **Every D/EG
number below is contingent on R1**; if R1 is answered the other way they shift
as a block.

> **Pre-existing defect found while writing this plan, not introduced by it:**
> `Gap Closure Plan — Network Policy.txt` numbers itself `D1–D10 / EG1–EG10`,
> which collides with the gate ledger's own D1–D10 (Gates 0–1). Two documents
> claim the same identifiers. This plan does not silently pick a side
> (CLAUDE.md §0); it is raised in §8 R1.

**Template note.** Each phase carries: Objective, Scope, Processes Activated,
Deliverables, Technical Detail, Exit Gate, Rollback. No SQL DDL or API contracts
apply — this is DNS, certificate lifecycle and configuration only — so Technical
Detail carries resource tables and decision rationale instead.

**Evidence labels** (CLAUDE.md §1): `VERIFIED` = observed directly in this repo
or the live system; `DOCUMENTED` = from official vendor docs, not confirmed
here; `ASSUMED` / `UNKNOWN` = must be proven before being relied on.

---

## 1. Current state

| Fact | Evidence | Label |
|---|---|---|
| Traefik v3.7.13, digest-pinned, `Deployment`, 1 replica, `kube-system` | `kubernetes/infrastructure/ingress/deployment.yaml` | `VERIFIED` |
| Entrypoints: `websecure` :8443 (TLS passthrough → Argo CD), `grafana-https` :8444 (TLS termination, Traefik default self-signed), `metrics` :8082 | same file + `service.yaml` | `VERIFIED` |
| NodePorts 32537 → websecure, 32538 → grafana-https; firewall publishes only those two | `service.yaml`, `ansible/roles/firewall/defaults/main.yml` | `VERIFIED` |
| Traefik providers: `kubernetescrd` only, namespaces `argocd,monitoring` | `deployment.yaml` args | `VERIFIED` |
| k3s `--service-node-port-range` unset → default **30000–32767** | `k3s-server/templates/config.yaml.j2` | `VERIFIED` |
| Platform DNS is `veridexeai.com` at **Squarespace** | `docs/evidence/gates/gate-00/closure.md:65` | `VERIFIED` |
| Squarespace exposes **no DNS-record API**, and no cert-manager DNS-01 solver exists for it | vendor docs + ecosystem survey, 2026-09-16 | `DOCUMENTED` |
| cert-manager vendored at **v1.21.2**, digest-pinned, Argo CD Application written (Phase 2, this branch); not yet applied to the cluster | `kubernetes/infrastructure/cert-manager/`, `gitops/infrastructure/cert-manager.yaml` | `VERIFIED` |
| Observability catalogue D06: "Certificate panels need cert-manager (not yet deployed)" | `docs/architecture/observability-catalogue.md:75` | `VERIFIED` |
| chrony synchronised on all 5 nodes (ACME requires sane clocks) | playbook run 2026-09-16 | `VERIFIED` |
| Cluster API access from the operator workstation is **currently down** | this session | `VERIFIED` |
| Whether Squarespace's DNS panel permits **`NS` records** on a subdomain | not checked — decides Phase 1's primary path | `UNKNOWN` |
| Whether the apex `veridexeai.com` currently serves a live site / MX records that must not be disturbed | not checked | `UNKNOWN` |
| `--enable-certificate-owner-ref` is **not set** in the vendored v1.21.2 manifest, so it takes the upstream default of `false` — deleting a `Certificate` does **not** delete its Secret | vendored `controller.yaml` args, checked 2026-09-16 | `VERIFIED` (flag absent) / `DOCUMENTED` (default is false) |

### 1.1 Why DNS-01, and what it removes

ACME offers two usable challenge types here. HTTP-01 is **fixed to port 80**;
TLS-ALPN-01 is fixed to port 443. Both are **below** this cluster's NodePort
range (30000–32767), so neither can simply be added to the Traefik NodePort
Service the way 32538 was — HTTP-01 would first require a low-port ingress
mechanism (a Traefik `DaemonSet` with `hostPort`, or nftables DNAT of uncertain
compatibility with Cilium's eBPF NodePort path).

**DNS-01 needs no inbound port at all.** Validation is proved by writing a TXT
record, an outbound-only operation. Choosing it deletes an entire phase of work
and its largest risk. Concretely, compared with Revision 1 this plan no longer
needs:

- any change to `kubernetes/infrastructure/ingress/deployment.yaml` — Traefik is
  untouched except for the one route that consumes the certificate;
- a `Deployment`→`DaemonSet` conversion, whose `kind` change has a window in
  which no Traefik pod exists, taking Argo CD **and** Grafana down together;
- `NET_BIND_SERVICE` on a container that currently drops all capabilities;
- an nftables DNAT spike whose interaction with Cilium `kubeProxyReplacement`
  was `UNKNOWN` and might simply not work;
- `--providers.kubernetesingress` on Traefik. HTTP-01's solver creates a plain
  `Ingress`, which Traefik's `kubernetescrd`-only configuration ignores
  entirely — the failure would have been silent. DNS-01 creates no Ingress.

It also removes the manual-DNS problem: records under the delegated zone become
API-managed and therefore reconcilable, rather than a human editing a web panel.

**Retained port suffix.** DNS-01 removes the requirement for port **80**. It does
not, by itself, remove the requirement for port **443** *if portless URLs are
wanted* — a certificate is valid for a hostname regardless of port, so
`https://grafana.k8s.veridexeai.com:32538/` serves a fully trusted certificate
with no browser warning. This plan deliberately accepts the port suffix and
**defers portless URLs to their own plan** (§9 R4), because that is the only part
that still needs low-port ingress surgery, and welding it to certificate issuance
is what made Revision 1 large and risky.

### 1.2 Corrections carried forward

Two statements made earlier in this engagement were wrong and are corrected here
rather than quietly dropped:

1. **"Open port 80 the same way I opened 32538."** Not possible — 32538 is a
   NodePort, 80 is below the NodePort range. This is what forced Revision 1's
   large Phase 1 and, ultimately, this rewrite.
2. **"Wildcards mean one certificate for everything."** Overstated. A wildcard
   `*.k8s.veridexeai.com` is now *possible* (HTTP-01 cannot issue wildcards at
   all), but Kubernetes Secrets are namespaced: a hostname in another namespace
   still needs its own `Certificate` and Secret there, and issuing the *same*
   wildcard in several namespaces creates duplicate certificates that consume a
   Let's Encrypt rate limit. Wildcards help when many hostnames share one
   namespace; they do not collapse a multi-namespace estate into one cert. This
   plan therefore issues a **single-hostname certificate** first (§4, Technical
   Detail) and records wildcard as available when it is actually justified.

---

## 2. Phase 1 — Delegated DNS zone under API control

**Objective** A subdomain of `veridexeai.com` is served by a DNS provider with a
record API, under an API credential scoped to that subdomain alone, so
cert-manager can complete DNS-01 challenges without any human editing records and
without the apex domain being touched.

**Scope**

- *In-Scope:* choose the delegating mechanism and provider; create the delegated
  zone; set the delegation at Squarespace; create a least-privilege API token;
  deliver that token to the cluster out-of-band; register it.
- *Out-of-Scope:* **any change to `veridexeai.com` apex records, its existing
  website, or its MX/TXT records**; moving the domain's registrar; migrating the
  apex nameservers (explicitly the last-resort fallback, not the plan).

**Processes Activated**

- *Delegated-zone DNS management* — owner: the chosen DNS provider's API, driven
  by cert-manager — drift detection: Phase 4's zone drift check (EG88).
- *Scoped DNS credential custody* — owner: operator workstation + out-of-band
  `kubectl` delivery — drift detection: `scripts/lint-secret-register.py` both
  ways, plus the token's own expiry if the provider supports one.

**Deliverables**

- **D63.** `docs/architecture/public-dns-delegation.md` — the chosen zone name,
  provider, delegation mechanism, the exact `NS` (or `CNAME`) records set at
  Squarespace, and why the apex was not moved. This is the reproduction
  instructions for the one manual step in the plan.
- **D64.** The delegated zone live at the provider, with `A` records for
  `grafana.<zone>` pointing at all five node public IPs (values sourced from
  `ansible/inventory/production/hosts.yml`, never retyped from memory).
- **D65.** A DNS API token scoped to **edit DNS records in the delegated zone
  only** — no account-wide, no other-zone, no non-DNS permission. Delivered to
  the cluster as a Secret applied out-of-band by `kubectl`, never committed.
- **D66.** `docs/security/secret-register.yml` — the token registered by name and
  location, no value, following the `grafana-admin-credentials` precedent
  (`manual_only: true` with a reviewed date, because no tracked file declares its
  manifest).
- **D67.** `docs/evidence/gap-closure/tls-public/phase1/` — delegation
  verification output: authoritative nameserver trace, and a TXT record written
  and read back **through the API**, proving cert-manager will be able to.

**Technical Detail**

**Delegation mechanism, in preference order.** The first that Squarespace
actually supports wins; this is decided by observation, not by this document.

| ID | Mechanism | What Squarespace must support | Consequence |
|---|---|---|---|
| **G1** | `NS` delegation of `k8s.veridexeai.com` to the provider | Adding `NS` records for a subdomain | Best outcome: everything under the subdomain is API-managed forever, including future hostnames. Apex untouched. |
| **G2** | `CNAME` of `_acme-challenge.<host>` to a zone under API control | Adding `CNAME` records (certain) | Works, but needs one static CNAME per hostname, set by hand once each. Apex untouched. cert-manager follows it with `cnameStrategy: Follow`. |
| **G3** | Move the whole domain's nameservers to the API-capable provider | — | **Last resort.** Every existing record (website, MX, verification TXT) must be recreated exactly or the site and email break. Largest blast radius in this plan. Requires its own authorization. |

**Provider choice is a decision, not an assumption (§8 R2).** The requirement is:
a free or near-free zone, a record API, a token that can be scoped to one zone,
and first-class cert-manager support (a native solver or a maintained webhook).
Candidates must be evaluated at build time against those criteria and the choice
recorded in D63. The provider must not be one this repository's provider-drift
policy excludes.

**Zone naming.** `k8s.veridexeai.com` is proposed. It is a DNS name, not a
Kubernetes namespace, so Gate 32 has no authority over it and there is no
ordering conflict — but it is a naming decision the repository owner may wish to
set differently, and it is cheap to change now and expensive later.

**The credential re-entangles this work with the open secrets decision, and that
must be stated plainly.** Revision 1's HTTP-01 design needed no credential at
all. DNS-01 needs a provider API token, which is a Secret — and the repo-wide
SOPS+age vs. Sealed Secrets decision is still open behind Gate 22's KMS incident
(the "§6 conflict"). This plan does **not** unblock or pre-empt that decision. It
uses the already-established out-of-band pattern: the value is applied with
`kubectl`, never committed, and only its name and location are registered
(exactly as `grafana-admin-credentials` was on 2026-09-16). EG87 asserts that no
secret value enters Git.

**Exit Gate**

- **EG68.** The delegated zone resolves authoritatively at the chosen provider —
  Method: trace delegation from the parent zone and confirm the provider's
  nameservers answer authoritatively for the delegated name — Result: PASS/FAIL.
- **EG69.** `grafana.<zone>` resolves to all five node public IPs, and returns
  **no `AAAA` record** — Method: query a public resolver for both `A` and `AAAA`
  — Result: PASS/FAIL. *(An `AAAA` record is not cosmetic: Let's Encrypt prefers
  IPv6 when one exists and fails rather than falling back, and this cluster's
  public path is IPv4-only.)*
- **EG70.** A TXT record can be created and deleted in the delegated zone **using
  the scoped token**, and the change is observable from a public resolver —
  Method: write, read back, delete — Result: PASS/FAIL. *(This is the exact
  capability DNS-01 needs; proving it here means a later challenge failure is
  not a credential problem.)*
- **EG71.** The token is **refused** when used against a zone or operation
  outside its scope — Method: attempt a record write in a different zone and an
  account-level read; both must be denied — Result: PASS/FAIL. *(CLAUDE.md §8:
  security tests must attempt the bypass, not just the happy path.)*
- **EG72.** The apex `veridexeai.com` is unchanged — Method: capture its full
  record set before and after Phase 1 and diff them; the existing site and any
  MX records must still resolve identically — Result: PASS/FAIL.

**Rollback** Remove the delegation records at Squarespace (the subdomain stops
resolving; nothing else is affected), revoke the API token at the provider, and
delete the in-cluster Secret. The apex was never modified, so there is no
data-loss surface and no path by which rollback can damage the existing website
or email. D63–D67 are documentation and evidence; reverting them is a Git revert.

---

## 3. Phase 2 — cert-manager platform install

**Objective** cert-manager runs in the cluster, pinned and GitOps-reconciled,
able to admit `Issuer` and `Certificate` objects.

**Scope**

- *In-Scope:* `cert-manager` namespace; CRDs; controller, webhook, cainjector;
  Argo CD Application with correct ordering and apply strategy; digest pinning.
- *Out-of-Scope:* issuing any certificate (Phase 3); `ClusterIssuer`; any change
  to Traefik.

**Processes Activated**

- *Certificate lifecycle management* — owner: cert-manager in-cluster — drift
  detection: Argo CD `selfHeal`; expiry alerting arrives in Phase 4 (EG86).

**Deliverables**

- **D68.** `kubernetes/cluster/namespaces/cert-manager.yaml` — the namespace.
  Required here rather than in the vendored manifest so exactly one Argo CD path
  owns it (CLAUDE.md §13), and because `scripts/lint-namespaces.py` fails CI on
  a manifest targeting an undeclared namespace.

  > **Corrected during build (2026-09-16).** This deliverable originally said
  > the namespace would be created "plain and unlabeled" per the O4 precedent.
  > That was wrong: the live `monitoring` namespace already carries
  > `veridex.io/owner` and `veridex.io/purpose` annotations (both **required**
  > by the namespace lint) plus `veridex.io/wave` and `veridex.io/role` labels.
  > The namespace follows that actual convention instead. wave/role remain
  > provisional — Gate 32 holds the authority to confirm or change them.
- **D69.** `kubernetes/infrastructure/cert-manager/crds.yaml` — vendored from the
  pinned upstream release, kept in its own file so it can occupy an earlier
  sync-wave, mirroring the existing `ingress/crds.yaml` house pattern.
- **D70.** `kubernetes/infrastructure/cert-manager/controller.yaml` — controller,
  webhook, cainjector, RBAC, Services. All images **digest-pinned**, with the
  digest verified against the registry at build time and the verification date
  recorded in a comment, exactly as `ingress/deployment.yaml` documents Traefik.
  v1.21.2 ships **no** `startupapicheck` Job, so there is none to remove
  (this deliverable originally assumed there was).
- **D71.** `gitops/infrastructure/cert-manager.yaml` — the Argo CD Application.

  > **Corrected during build (2026-09-16).** Originally written as a file inside
  > a `cert-manager/` subdirectory, "replacing the `.gitkeep` placeholder". On
  > `main` there is no such directory and no placeholder — every Application
  > under `gitops/infrastructure/` is a **flat file**. The subdirectory layout
  > exists only on the unmerged `fix/monitoring-data-ownership` branch. Built to
  > match `main`.
- **D72.** PR/commit text carrying the written justification CLAUDE.md §13
  requires for cluster-scoped resources (CRDs, ClusterRole, webhook
  configurations).

**Technical Detail**

- **Version: v1.21.2**, resolved at build time (2026-09-16) and no longer
  `UNKNOWN`. Chosen over the v1.20.4 patch published the same week because
  v1.20.4's own notes state three `golang.org/x/crypto` findings remain unfixed
  in the 1.20 line and direct users to 1.21 for a clean scan. 1.21.2 also carries
  ACME fixes in this cluster's exact path: a renewal-window bug on 29 February
  cron schedules, ACME response bodies capped against unbounded-body DoS, and
  ACME response content no longer copied into Issuer status or Events. Upstream
  manifest sha256 `e03b668e…79f`, recorded in the vendored files' headers.
- **`ServerSideApply=true` is mandatory.** cert-manager's CRDs exceed the
  262 144-byte limit on the `last-applied-configuration` annotation, so a
  client-side apply fails outright:
  ```yaml
  syncPolicy:
    syncOptions: [ServerSideApply=true]
    automated: {prune: true, selfHeal: true}
    retry: {limit: 5, backoff: {duration: 15s, factor: 2, maxDuration: 3m}}
  ```
  `retry` matters because `Issuer`/`Certificate` objects are rejected until the
  webhook is serving; retry converges instead of failing the sync.
- **Sync ordering.** The Application carries `sync-wave: "2"`. *Within* the
  Application, CRD-before-controller ordering relies on Argo CD's built-in kind
  ordering rather than per-resource `sync-wave` annotations — annotating the six
  vendored CRDs would mean hand-editing ~1 MB of upstream content that is marked
  DO-NOT-HAND-EDIT, and would have to be redone at every version bump. The
  `retry` block is what makes this safe: if the controller is applied before its
  CRDs are established, the sync retries and converges.
- **`Issuer`, not `ClusterIssuer`.** CLAUDE.md §13 prefers namespace-scoped
  resources and requires written justification for cluster-scoped ones. A
  namespace-scoped `Issuer` in `monitoring` is sufficient for the first
  certificate; promotion is deferred to the moment a second namespace needs one.
  Note the consequence: the DNS token Secret must exist in each namespace that
  holds an `Issuer`, which is a real cost of the namespace-scoped choice and is
  accepted deliberately.

**Exit Gate**

- **EG73.** All cert-manager pods Ready and the webhook serving — Method:
  `kubectl get pods -n cert-manager` plus a webhook admission probe — Result:
  PASS/FAIL.
- **EG74.** Argo CD reports the cert-manager Application `Synced`/`Healthy` at
  the merge commit — Method: read `.status.sync.revision`, `.status.sync.status`
  and `.status.health.status`, confirming the revision equals the merge commit —
  Result: PASS/FAIL.
- **EG75.** Every cert-manager image runs by **digest**, not tag — Method:
  inspect the running pod specs — Result: PASS/FAIL.
- **EG76.** CI passes: `lint-namespaces.py`, `lint-secret-register.py`,
  `lint-provider-drift.py`, YAML lint — Method: the PR's CI run, with
  provider-drift compared error-for-error against its count on `main` at the same
  commit rather than against zero (see §8 R3) — Result: PASS/FAIL.
- **EG77.** Deleting a cert-manager pod results in automatic recovery to Ready
  with no manual action — Method: delete the controller pod and observe —
  Result: PASS/FAIL. *(Named explicitly by `sequential-service-build-plan.md:81`:
  "verify controller recovery".)*

**Rollback** Revert D71 (Argo CD prunes controller, webhook, cainjector) then
D68–D70. **Delete CRDs last and deliberately:** removing a CRD removes every
`Certificate` object of that type.

Executed in order — rolling Phase 2 back before Phase 3 has run — there is no
data-loss surface, because no certificate exists yet. The CRD warning concerns
the one genuinely dangerous case: rolling Phase 2 back **after** Phase 3 has
issued. In that case complete Phase 3's rollback first, and back up every
`kubernetes.io/tls` Secret to the operator workstation before starting, because
losing a certificate and re-issuing consumes Let's Encrypt rate limit.

---

## 4. Phase 3 — First Let's Encrypt certificate, staging then production

**Objective** `grafana.k8s.veridexeai.com` serves a publicly-trusted Let's
Encrypt certificate, issued by DNS-01, with no browser warning.

**Scope**

- *In-Scope:* ACME `Issuer` against Let's Encrypt **staging** first, then
  production, both with a DNS-01 solver using the Phase 1 token; a `Certificate`
  for the one hostname; the Grafana route updated to serve it.
- *Out-of-Scope:* wildcard certificates (§1.2); certificates for Argo CD or any
  other service; retiring NodePort 32538; portless URLs.

**Processes Activated**

- *ACME DNS-01 issuance and renewal* — owner: cert-manager — drift detection:
  Phase 4's renewal proof (EG85), expiry alert (EG86) and zone drift check
  (EG88).

**Deliverables**

- **D73.** `kubernetes/infrastructure/monitoring/acme-issuer-staging.yaml` — ACME
  `Issuer`, Let's Encrypt **staging** endpoint, DNS-01 solver referencing the
  Phase 1 token Secret by name.
- **D74.** `kubernetes/infrastructure/monitoring/acme-issuer-prod.yaml` — the
  same against the production endpoint.
- **D75.** `kubernetes/infrastructure/monitoring/grafana-certificate.yaml` — a
  `Certificate` for `grafana.k8s.veridexeai.com`, `secretName: grafana-tls`, in
  `monitoring`.
- **D76.** `kubernetes/infrastructure/monitoring/grafana-ingressroute.yaml` —
  the existing route gains `Host(...)` matching and
  `tls.secretName: grafana-tls`, replacing Traefik's default self-signed
  certificate. It stays on the existing `grafana-https` entrypoint and NodePort
  32538; no Traefik Deployment change is required anywhere in this plan.
- **D77.** `docs/evidence/gap-closure/tls-public/phase3/` — staging order
  transcript, production order transcript, the issued chain, and the
  external verification output.
- **D78.** The Let's Encrypt rate limits as published **on the build date**,
  recorded verbatim, so a later reader knows which limits the plan was executed
  under rather than inferring from a stale figure.

**Technical Detail**

- **Staging first is mandatory.** Production enforces rate limits
  (`DOCUMENTED`); the ones a debugging loop hits are the duplicate-certificate
  and failed-validation limits. Exact thresholds are deliberately not quoted in
  this plan — they change, and a stale number invites a wrong decision. Read them
  at build time and record them in D78. Production issuance happens only after
  the identical configuration has succeeded against staging.
- **Certificate and route must share a namespace.** A Traefik `IngressRoute`'s
  `tls.secretName` resolves in its own namespace, so the `Certificate` is created
  in `monitoring`, not `cert-manager`.
- **Single hostname, not wildcard** — see §1.2. Wildcard is available under
  DNS-01 and should be adopted when several hostnames genuinely share one
  namespace, at which point the duplicate-certificate limit and the blast radius
  of one private key covering every subdomain both need weighing.
- **If EG79 fails, check propagation before retrying.** The usual DNS-01 failure
  is not a bad credential but the challenge TXT record not yet visible to Let's
  Encrypt's resolvers. cert-manager self-checks propagation before asking for
  validation; repeated blind retries burn failed-validation quota. Confirm the
  TXT record is externally visible first — EG70 already proved the token can
  write it.
- **No change to the Argo CD path.** Argo CD keeps its `HostSNI(*)` TLS
  passthrough on 32537 throughout. This plan does not touch it, and EG84 proves
  it.

**Exit Gate**

- **EG78.** The DNS-01 solver completes a challenge against **staging** —
  Method: observe the `Challenge` object reach valid and the TXT record appear
  and be cleaned up afterwards — Result: PASS/FAIL.
- **EG79.** A certificate issues successfully against **staging** — Method: apply
  the Certificate against the staging Issuer and observe `Ready=True` with Order
  and Challenge both succeeding — Result: PASS/FAIL.
- **EG80.** A certificate issues against **production**, and
  `https://grafana.k8s.veridexeai.com:32538/` presents a chain that validates
  against the system trust store — Method: `curl` **without** `-k`, plus one real
  browser load — Result: PASS/FAIL.
- **EG81.** The served certificate's issuer is Let's Encrypt and its SAN list is
  exactly the one hostname — Method: inspect the served chain's issuer and SAN
  list from outside the cluster; no extra names — Result: PASS/FAIL.
- **EG82.** **Adversarial:** a `Certificate` for a hostname outside the delegated
  zone fails to issue and produces no usable Secret — Method: request one against
  **staging**, observe failure, delete it — Result: PASS/FAIL.
- **EG83.** **Adversarial:** the challenge TXT record is removed after
  validation, leaving no stale `_acme-challenge` record behind — Method: query
  the zone after issuance — Result: PASS/FAIL. *(A solver that leaks records
  accumulates them until the zone is unmanageable and leaks which hostnames
  exist.)*
- **EG84.** Argo CD on 32537 and Grafana's pre-existing behaviour are both
  unaffected — Method: probe both and compare against the responses recorded
  before the phase — Result: PASS/FAIL.

**Rollback** Revert D76 — Traefik falls back to its default self-signed
certificate on the same entrypoint and port, which is exactly the pre-plan state
and is regenerated automatically — then D73–D75. Back up the `grafana-tls` Secret
**before** the revert: cert-manager's `--enable-certificate-owner-ref` default
must be confirmed at build time (`UNKNOWN` here), and if it is enabled, Argo CD
pruning the `Certificate` takes the live certificate with it. The DNS records are
left in place; they are harmless and removing them only lengthens the next
attempt.

---

## 5. Phase 4 — Renewal, observability, and drift control

**Objective** The certificate demonstrably renews without human action, its
expiry and the zone it depends on are both monitored, and the plan's record is
closed.

**Scope**

- *In-Scope:* forced-renewal proof; cert-manager metrics and expiry alerting;
  a zone drift check; recording the out-of-gate drift already introduced by
  PRs #51/#52; the closure record.
- *Out-of-Scope:* portless URLs (§9 R4); Gate 30 egress policy for cert-manager
  (recorded as a forward dependency, not built here).

**Processes Activated**

- *Certificate expiry alerting* — owner: VictoriaMetrics/vmalert + Alertmanager —
  drift detection: alert on approaching expiry or on renewal failure.
- *Delegated-zone drift detection* — owner: a scheduled check — drift detection:
  fails if the delegation or the `A` records stop matching what D63/D64 declare.

**Deliverables**

- **D79.** `kubernetes/infrastructure/monitoring/` — vmagent scrape config for
  cert-manager metrics plus vmalert rules for approaching expiry and for
  `certmanager_certificate_ready_status == 0`. Closes the known-partial D06 row
  in the observability catalogue.
- **D80.** `docs/architecture/observability-catalogue.md` — D06 updated from
  **Partial** to what now exists.
- **D81.** A scheduled check asserting the delegation still points at the
  provider and `grafana.<zone>` still resolves to the five expected IPs, with
  failures surfaced the same way other checks are.
- **D82.** `docs/evidence/gap-closure/tls-public/prior-drift.md` — a dated record
  that PRs #51/#52 changed Traefik and the host firewall **after** Gate 11
  closed, outside any gate's evidence chain, including that the first Ansible run
  of 2026-09-16 applied an unchanged ruleset (a no-op) because it ran against a
  working tree lacking the merged change. Raises, without deciding, whether
  Gate 11 warrants a reopen-log entry (§8 R5).
- **D83.** `docs/evidence/gap-closure/tls-public/closure.md` — written **last**:
  what was built, every EG with its method and result, residual risks, and the
  plan commit plus repo commit tested.

**Technical Detail**

- **Renewal cannot be proven by waiting.** cert-manager renews at ~2/3 of a
  90-day lifetime. Renewal is proven by forcing one against the **staging**
  issuer and observing a new `notAfter` and a new Secret revision, leaving the
  production rate limit untouched.
- **Forward dependency, not built here:** when the P0–P6 NetworkPolicy promotion
  reaches these namespaces (Gate 30), cert-manager will need explicit egress to
  the ACME endpoints **and to the DNS provider's API**. DNS-01 adds the second of
  those; recorded now so it is not discovered as an outage later.

**Exit Gate**

- **EG85.** A forced renewal against staging produces a new certificate with a
  later `notAfter` and no manual intervention — Method: trigger reissue, then
  compare `notAfter` and the Secret's resource version before and after —
  Result: PASS/FAIL.
- **EG86.** The expiry alert rule loads in vmalert and fires against a
  deliberately-near-expiry condition — Method: evaluate the rule against a
  synthetic series — Result: PASS/FAIL.
- **EG87.** No secret value entered Git: `lint-secret-register.py` passes and no
  `kind: Secret` manifest was added — Method: CI plus a diff review of every
  commit in the plan — Result: PASS/FAIL.
- **EG88.** The zone drift check fails against a deliberately wrong expectation
  and passes against the real records — Method: run it twice, once with a
  corrupted expected-IP list (must FAIL) and once as shipped (must PASS) —
  Result: PASS/FAIL. *(A check never seen to fail is not known to work.)*
- **EG89.** **IIR proof:** a full re-run — `prepare-hosts.yml`, plus an Argo CD
  hard-refresh and re-sync of `traefik`, `monitoring` and `cert-manager` —
  produces `changed=0` on Ansible, `Synced` with no diff on all three
  Applications, and **no certificate re-issuance** — Method: compare the
  certificate's `notAfter` and Secret resource version before and after; both
  unchanged — Result: PASS/FAIL. *(A re-sync that recreates the `Certificate` and
  triggers a new ACME order would be both non-idempotent and a rate-limit
  consumer.)*

**Rollback** D79–D81 and D82–D83 are additive rules and documentation; revert is
a Git revert with no cluster data-loss surface.

---

## 6. Cumulative deliverable and exit-gate index

| Phase | Deliverables | Exit gates |
|---|---|---|
| 1 — Delegated DNS zone | D63–D67 | EG68–EG72 |
| 2 — cert-manager install | D68–D72 | EG73–EG77 |
| 3 — First certificate | D73–D78 | EG78–EG84 |
| 4 — Renewal, observability, drift | D79–D83 | EG85–EG89 |

**Totals:** D63–D83 (21 deliverables), EG68–EG89 (22 exit gates).

---

## 7. Preconditions before Phase 1 may start

- **P1.** Cluster API access restored from the operator workstation (currently
  down — the kubeconfig targets `127.0.0.1:16443` with no tunnel running). Every
  exit gate from Phase 2 onward requires it.
- **P2.** Every `UNKNOWN` row in §1 resolved by observation, not inference —
  in particular whether Squarespace permits `NS` records on a subdomain (which
  decides G1 vs G2), and what the apex currently serves (which bounds EG72).
- **P3.** Decisions R1–R3 in §8 answered.

---

## 8. Decisions required from the repository owner

- **R1 — Deliverable numbering.** Confirm this plan consumes D63–D83 /
  EG68–EG89 (Gate 12 then begins at D84/EG90), or direct that gap-closure work
  use a separate namespace of identifiers. Related: the pre-existing D1–D10
  collision noted in §0 needs a ruling either way.
- **R2 — DNS provider and zone name.** Which API-capable provider hosts the
  delegated zone, and is `k8s.veridexeai.com` the name you want? Cheap now,
  expensive after certificates and records exist.
- **R3 — CI baseline.** `lint-provider-drift.py` currently fails on `main` with
  36 pre-existing errors, all in `gitops/policies/README.md` and unrelated to
  this plan. EG76 is written against that baseline. Confirm that is acceptable,
  or that the baseline is fixed first.
- **R4 — Portless URLs.** This plan accepts `:32538` in the URL. Removing it
  needs low-port ingress (a Traefik `DaemonSet` with `hostPort`, or a DNAT
  mechanism of unproven compatibility with Cilium here) and should be its own
  plan with its own spike. Confirm that deferral.
- **R5 — Gate 11 drift.** PRs #51/#52 modified Traefik and the host firewall
  after Gate 11 closed. Reopen-log entry, or is recording it as gap-closure
  drift (D82) sufficient?

---

## 9. Residual risks

1. **A new third-party dependency in the certificate path.** Certificate renewal
   now depends on the DNS provider's API being reachable and the token still
   valid, in addition to Let's Encrypt. Two external dependencies, not one.
   Expiry alerting (D79) is what makes either failure visible before it becomes
   an outage.
2. **The DNS token is a standing credential.** It can edit records in the
   delegated zone for as long as it exists. It is scoped to one zone (EG71 proves
   the scoping), but it does not expire unless the provider supports expiry, and
   there is no rotation process in this plan. Rotation belongs with the wider
   secrets decision behind Gate 22.
3. **This re-entangles the work with the open secrets decision.** Revision 1
   needed no credential; this revision does. The out-of-band pattern keeps it out
   of Git, but it is a step backwards on that axis and was chosen knowingly.
4. **Public exposure is unchanged but now discoverable.** Grafana moves from an
   obscure IP:port to a memorable hostname while keeping anonymous Viewer access.
   Two mitigations exist and neither is taken here: set
   `GF_AUTH_ANONYMOUS_ENABLED=false` so the hostname requires login, or accept
   it. The cheap moment to decide is before the hostname is shared, not after.
5. **Argo CD remains on a port with a catch-all route.** Giving it
   `argocd.k8s.veridexeai.com` later means either moving it off TLS passthrough
   onto Traefik-terminated TLS, or SNI-routing 443 between two TCP backends — and
   its `HostSNI(*)` catch-all makes the second impossible until that route is
   scoped to a hostname, which its own file already flags as owed work.
6. **A from-scratch rebuild re-issues certificates** and can hit the
   duplicate-certificate limit if rehearsed repeatedly in one week. Any rebuild
   drill must point at the **staging** issuer. This belongs in the backup/DR
   runbook when it is written (CLAUDE.md §2 records it as not yet written).

---

## 10. Immutability, idempotence, repeatability (IIR)

CLAUDE.md §4 requires permanent changes to be declarative, version-controlled,
reproducible and reversible. Stated per class, because "it's in Git" and "a
rebuild reproduces it" are different claims:

| Class | Deliverables | Immutable | Idempotent | Repeatable on a rebuild |
|---|---|---|---|---|
| Delegation records at Squarespace | D63 (documents them) | No — a web panel | No | **No — manual, but set once and static** |
| Records inside the delegated zone | D64 | Yes — API-managed | Yes — re-applying converges | Yes |
| DNS API token | D65, D66 | Value never in Git; name registered | Re-applying the Secret converges | Manual re-issue at the provider |
| cert-manager platform | D68–D72 | Yes — images digest-pinned (EG75), CRDs vendored at a fixed release | Yes — Argo CD sync converges; `retry` absorbs webhook-not-ready | Yes |
| Issuers and Certificate | D73–D75 | Yes — declarative objects | Yes — EG89 requires a re-sync to cause **no** re-issuance | Partly — a rebuild re-issues (§9.6) |
| Grafana route | D76 | Yes | Yes — Argo CD `selfHeal` | Yes |
| Observability rules, drift check | D79–D81 | Yes | Yes | Yes |
| Documentation and evidence | D63, D67, D77, D78, D82, D83 | Yes — append-only, repo evidence style | N/A | Yes |

**Where this plan is still not fully repeatable, stated plainly:**

1. **The delegation itself is manual** — `NS` (or `CNAME`) records set by hand at
   Squarespace, because Squarespace has no API. This is a **one-time, static**
   step, unlike Revision 1 where *every* record was manual and every new hostname
   meant another human edit. Everything beneath the delegation is API-managed.
   That is the single largest IIR improvement of this revision.
2. **A rebuild re-issues certificates** (§9.6) — correct behaviour, but
   rate-limited, so rehearsals use staging.

**No hand-run command is load-bearing.** Every change lands through Ansible or
Argo CD. `kubectl` is used only to *observe*, to *deliver the DNS token
out-of-band*, and to *back up a Secret before a destructive rollback* — never as
the means of applying a permanent change (CLAUDE.md §15).
