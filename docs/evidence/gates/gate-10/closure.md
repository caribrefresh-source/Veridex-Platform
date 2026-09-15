# GATE 10 — Argo CD handover

| | |
|---|---|
| **Verdict** | **PASS** — see the Stop Condition deviation note below before trusting this verdict at face value |
| **Closed (UTC)** | 2026-09-15T09:20:00Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `bc27a0a2b9e872679007342b5d255b888e000722`, sha256 `0c30445b0074edf3688ba57936e1c5149497b829e0f7d1b4328c5181bd222af8` (blob in Git) |
| **Tested repo commit** | `145df11e4220e88c85c86952ae089a06bf9061a4` (`main`, after merging PR #15 `98dadd7` and PR #16 `ed366ea`; matches every evidence file's own `repo_commit:` field) |
| **Target identity** | kube-system namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API `https://127.0.0.1:6443` (veridex-server-1's local k3s admin kubeconfig) |
| **High-risk** | Yes — CRDs/operators (CLAUDE.md §12): installing Argo CD's 59-resource manifest onto the live production control plane |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given the diff and Gate 10 plan text). Found 5 issues (1 high, 1 medium-high, 1 medium, 2 low); the medium-high (root app sourced from the control node's working tree rather than origin/main), medium (unquoted Jinja interpolation) and both lows were fixed and reverified live. The high (unverified PAT scope) was investigated, confirmed as a real, serious finding, and disposed of by explicit user decision rather than a code fix — see below. |

**⚠ Stop condition deviation — read before trusting the PASS verdict.** Gate
10's stop condition includes "writable repo key." The `ARGOCD_REPO_PAT`
deployed to `Secret argocd-repo-veridex-platform` was confirmed live
(`pat-scope-finding.txt`) to be a classic GitHub PAT with near-full
account-admin scope (`admin:org`, `admin:enterprise`, `delete_repo`, `repo`,
`workflow`, and more) — not read-only, and not minted for this gate (the
operator selected it from an existing personal credentials file containing
several unrelated secrets). This is the stop condition, triggered, on a
plain reading of the plan's text. Per this skill's own rule ("Evaluate the
stop condition verbatim; if triggered, the gate is FAIL regardless of check
results"), the default outcome would be FAIL. The operator was shown the
exact scope list, told explicitly that keeping this credential means the
stop condition is triggered and the plan's rule makes that an automatic
FAIL, and — asked a second time to confirm — explicitly directed that Gate
10 close as **PASS**, with this recorded as a residual risk rather than a
blocking failure. This record honors that instruction while stating it as
plainly as possible: **every check below passed on its own merits; the
verdict is PASS only because of an explicit, disclosed operator override of
the plan's own stop-condition rule, not because the stop condition was found
not to apply.**

## 1. OBJECTIVE

> Pinned Argo CD is healthy. Repository access is read‑only. Bootstrap,
> verification, Argo controller and emergency identities are separate.
> Cilium and CoreDNS ownership is singular and documented.

## 2. SCOPE

**In scope**
- Installing pinned, checksum-verified Argo CD v3.5.3 (plain manifest, not
  Helm) onto the production cluster via Ansible, with `--server-side` apply
  where client-side apply proved broken for this manifest (the
  `applicationsets.argoproj.io` CRD exceeds the 262144-byte
  last-applied-configuration annotation limit under client-side apply).
- A least-privilege RBAC overlay on `argocd-rbac-cm` (which ships with no
  `data:` at all), setting an explicit `policy.default` instead of relying
  on Argo CD's implicit fallback.
- Rotating the auto-generated initial admin password to a random value that
  is never stored anywhere (bcrypt-hashed offline via `argocd account
  bcrypt`, patched directly into `argocd-secret`, the initial secret
  deleted) — operational access uses the operator's existing root SSH key
  (`--core` mode) or project-role JWT tokens, never the admin password.
- The `veridex` AppProject (this repo, this cluster only) and the app-of-apps
  root Application, applied as the one necessary imperative bootstrap step;
  everything downstream is GitOps-reconciled from `gitops/` on `main`.
- Documenting Cilium (Ansible/Helm-owned) and CoreDNS (k3s-native-owned) as
  permanently outside GitOps, with the enforcement rationale for reviewers.
- Live proof of all five acceptance-evidence items (§6).

**Out of scope**
- Namespace enumeration for later rollout waves → Gate 32, per this gate's
  own gap-closure note ("once GitOps can manage manifests, every namespace
  name ... must be resolved and committed before any wave begins").
- Replacing the over-scoped `ARGOCD_REPO_PAT` with a properly-scoped one →
  flagged as a recommended follow-up, not performed here (see the Stop
  Condition deviation note above and `pat-scope-finding.txt`).
- Exposing Argo CD's UI/API via Ingress → not needed for this gate; all
  verification used `--core` mode or a manually-managed `kubectl
  port-forward`.
- Any actual application workloads under `gitops/applications/` — still
  empty placeholders; this gate proves the mechanism, not a populated
  rollout.

## 3. PROCESSES ACTIVATED

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| Argo CD reconciliation of everything under `gitops/` (excluding `bootstrap/**`) from `main`, automated with `prune: true, selfHeal: true` | Argo CD itself, bootstrapped by Ansible (`roles/argocd-bootstrap`) | `kubectl -n argocd get application root` showing a stale `.status.sync.revision` against `git rev-parse origin/main`, or `Health Status` leaving `Healthy` |
| Argo CD's own control-plane pods (server, repo-server, application-controller, redis, dex, notifications, applicationset-controller) | k3s (standard Deployment/StatefulSet reconciliation) | Standard pod readiness/restart-count monitoring — no gate-specific alerting added |
| Least-privilege RBAC (`argocd-rbac-cm`, the `veridex` AppProject's `readonly` role) | Ansible (`roles/argocd-bootstrap`) for the ConfigMap overlay; Argo CD itself for the AppProject once merged | A project-role JWT successfully performing `sync`/`delete` would be the detection signal — exercised once in this gate's own evidence (§6, EG52) and not automated as a recurring check |

## 4. DELIVERABLES

| ID | Artifact | Commit |
|---|---|---|
| D48 | `ansible/roles/argocd-bootstrap/` — install, RBAC overlay, admin-password rotation, imperative AppProject/root-app apply, all fixes found live and from independent review | `7fb4756`, `aae53bb`, `ed366ea` |
| D49 | `gitops/projects/veridex.yaml` — the `veridex` AppProject | `7fb4756` |
| D50 | `gitops/bootstrap/root-application.yaml` — `project: veridex` (not `default`), `directory.recurse: true` with `exclude: "bootstrap/**"` | `7fb4756` |
| D51 | `docs/security/cilium-coredns-ownership.md` | `7fb4756` |
| D52 | `docs/security/secret-register.yml` — `ARGOCD_REPO_USERNAME`/`ARGOCD_REPO_PAT`/the repo-credential Secret marked active, with the PAT-scope finding documented in place | `7fb4756` |
| D53 | `docs/evidence/gates/gate-10/` — this record and its six evidence files | (this commit) |

## 5. TECHNICAL DETAIL

**Resource tables**
- Argo CD v3.5.3 install manifest: 59 resources across 11 kinds (2 CRDs, 6
  ServiceAccounts, 6 Roles, 3 ClusterRoles, 6 RoleBindings, 3
  ClusterRoleBindings, 7 ConfigMaps, 2 Secrets, 8 Services, 6 Deployments, 1
  StatefulSet, 7 NetworkPolicies), checksum `sha256:7efe2d6bbc03f63623640f1e4198f16c84009d510fb810ef71e56df1b7614ba9`.
- `gitops/projects/veridex.yaml`: `sourceRepos` restricted to this repo;
  `destinations` restricted to `https://kubernetes.default.svc` (this
  cluster only, never an external/registered cluster — the "unrestricted
  destinations" stop condition); `clusterResourceWhitelist` restricted to
  `Namespace` only; one project role (`readonly`) with explicit `deny` on
  `sync`/`delete`/`override`/`action/*`.

**Decision rationale**
- *Namespace stays `'*'` within the one restricted cluster, not further
  narrowed*: Gate 10's own gap-closure note places namespace enumeration at
  Gate 32, which runs after GitOps exists to manage it — narrowing now would
  mean guessing names Gate 32 hasn't decided yet.
- *`clusterResourceWhitelist` pre-approves only `Namespace`*: the same
  gap-closure note implies future namespaces will be Argo-managed (unlike
  the `argocd` namespace itself, Ansible's sole bootstrap exception). Nothing
  else cluster-scoped is pre-approved by default.
- *Admin password rotated via direct `argocd-secret` patch, not
  `argocd account update-password`*: `--core` mode cannot call the account
  API (it talks to CRDs directly, not `argocd-server`'s auth subsystem), and
  this is Argo CD's own documented manual-reset procedure — avoids any
  dependency on port-forward/login session state for a one-time rotation.
- *`--server-side --force-conflicts` used throughout, not client-side apply*:
  found live to be necessary for four distinct objects during this gate's
  own build — the `applicationsets.argoproj.io` CRD (annotation size limit),
  the repo-credential Secret (a `stringData` Secret's live object only ever
  has `data`, so client-side apply's diff never converges to "unchanged"),
  the RBAC ConfigMap overlay (created by the install manifest's own
  server-side apply; a later plain client-side apply on top never converged
  either), and the `veridex` AppProject once Argo CD itself began
  reconciling it (a second, Argo-owned field-manager disagreeing with plain
  client-side apply on every rerun). `--force-conflicts` is safe in every
  case: this playbook is the sole non-Argo field-manager for every object it
  applies.
- *Root app manifests sourced from `origin/main` via `git show`, not the
  control node's working tree*: found by independent review — a plain
  `copy` from the working tree would silently apply whatever happened to be
  checked out locally (including this gate's own feature branch) while every
  check reports "root app from main." Fixed by fetching and rendering from
  `origin/main` explicitly on the control node before copying to the
  bootstrap server.
- *The PAT-scope finding (full account-admin, not read-only)*: see the Stop
  Condition deviation note above and `pat-scope-finding.txt` for the full
  investigation, including two red-herring 401s from header-based auth
  attempts that were superseded by a definitive Basic-Auth scope check.

## 6. EXIT GATE

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG52 | Denied-action RBAC matrix | A project-role JWT (`proj:veridex:readonly`) tested live against the real Argo CD API: `get` allowed, `sync` and `delete` explicitly denied with `PermissionDenied` errors naming the exact subject/action/resource | `c1-rbac-matrix.txt` | **PASS** — a first attempt was invalidated and caused a disclosed production incident (a stale CLI login context silently bypassed the token under test, resulting in an accidental `sync`/`delete` of the live `root` Application; remediated within minutes, blast radius confined to that one object); the corrected retest is the evidence supporting PASS |
| EG53 | Root app from main | `spec.source.targetRevision`/`repoURL` inspected; synced revision compared against an independently-fetched `git rev-parse origin/main`, after a hard refresh | `c2-root-app-from-main.txt` | **PASS** — `targetRevision=main`; synced revision `145df11e4220e88c85c86952ae089a06bf9061a4` matches `origin/main` HEAD exactly |
| EG54 | Sync/Healthy | `kubectl get application root` status fields; Argo CD's own control-plane pod readiness | `c3-sync-healthy.txt` | **PASS** — `Sync Status: Synced`, `Health Status: Healthy`, all 7 Argo CD control-plane workloads Running/Ready |
| EG55 | No duplicate Helm owner | Enumerated every Argo Application and its destination; every Helm release history in the cluster; Cilium/CoreDNS's own ownership labels | `c4-no-duplicate-helm-owner.txt` | **PASS** — only `root` exists (destination: `argocd` only); Cilium's 6 Helm releases are all Ansible-CLI-driven; CoreDNS carries k3s's own `objectset.rio.cattle.io` label, not Helm |
| EG56 | Drift test reverted by correct owner | Hand-patched the live, Argo-managed `veridex` AppProject's description via `kubectl patch`; polled for Argo CD's own `selfHeal` to revert it | `c5-drift-test.txt` | **PASS** — reverted within the first 5-second poll interval, no manual intervention; `root` stayed Synced/Healthy throughout |

**Stop condition (verbatim):** "Admin kubeconfig in workflow, writable repo
key, duplicate ownership, unrestricted destinations, or manual live
manifest."

**Triggered: yes — "writable repo key."** See the deviation note at the top
of this record and `pat-scope-finding.txt` for the full finding and its
disposition. The other four clauses are not triggered:
- *Admin kubeconfig in workflow:* the root Application's destination is
  `https://kubernetes.default.svc` (in-cluster); no external kubeconfig is
  ever registered as an Argo CD Cluster secret. Operational access uses
  `--core` mode (the operator's own existing root SSH key) or project-role
  JWTs, never the raw admin kubeconfig embedded in a workflow.
- *Duplicate ownership:* EG55, PASS — verified live, no second owner exists
  for anything Argo CD manages, and Cilium/CoreDNS are confirmed outside
  Argo CD's scope entirely.
- *Unrestricted destinations:* `gitops/projects/veridex.yaml` restricts
  `destinations` to this one cluster's in-cluster API server — not `*`
  server, not an external/attacker-registered cluster.
- *Manual live manifest:* the one manual `kubectl apply` step (the AppProject
  and root Application) is the plan's own necessary one-time bootstrap
  exception, sourced from `origin/main` (not hand-edited), and everything
  downstream is GitOps-reconciled, not hand-patched.

## 7. ROLLBACK

### 7.1 Reversal procedure

**Repo-side (reversible, IIR-safe):** `git revert` of `7fb4756`, `aae53bb`
and `ed366ea` (in reverse order) removes the RBAC overlay template, the
`veridex` AppProject manifest, the Cilium/CoreDNS ownership doc, and reverts
`root-application.yaml`'s `project`/`directory` fields and the
`argocd-bootstrap` role to its pre-Gate-10 (repo-credential-only) state.

**Cluster-side:** `kubectl delete -f <the pinned install manifest>` removes
all 59 Argo CD resources; the `argocd` Namespace itself is Ansible-owned
(`gitops/bootstrap/namespace.yaml`) and survives independently. The
`veridex` AppProject and `root` Application can be deleted individually
(`kubectl delete appproject veridex -n argocd`, `kubectl delete application
root -n argocd`) without touching anything else, since `gitops/`'s other
directories hold no real workloads yet.

**Credential-side:** the repo-credential Secret can be deleted
(`kubectl delete secret argocd-repo-veridex-platform -n argocd`) and the
`ARGOCD_REPO_USERNAME`/`ARGOCD_REPO_PAT` unset from the operator's
environment; nothing else depends on them. The rotated admin password is
not recoverable by design (never stored) — a fresh reinstall would
auto-generate a new initial password, rotated the same way on the next
`bootstrap-argocd.yml` run.

Nothing in this gate is IRREVERSIBLE.

### 7.2 Adversarial hardening loop

One iteration (cap 11).

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | (a) Live testing while building and proving the role end-to-end; (b) independent review (Tier 1, separate context, given the diff and Gate 10 plan text) | **(a) 6 real issues found by running it:** client-side apply exceeding the 262144-byte annotation limit on the ApplicationSet CRD; a `stringData` Secret's client-side apply never converging to "unchanged"; the repo-credential label-check jsonpath losing its backslash escapes through `command`'s shlex string-splitting; a YAML folded-scalar continuation line silently preserved as a literal newline, splitting the admin-password-rotation `kubectl patch` in two; the control node's own git having no stored GitHub credential once a `git fetch` task was added; the `veridex` AppProject's apply never converging to "unchanged" once Argo CD itself began reconciling it. **(b) 5 findings from independent review:** HIGH — `ARGOCD_REPO_PAT`'s scope never independently verified (investigated further, confirmed as a real, serious finding — disposed of by explicit operator decision, not a code fix, see the Stop Condition deviation note); MEDIUM-HIGH — root app manifests sourced from the control node's working tree instead of `origin/main`; MEDIUM — unquoted Jinja interpolation in the repo-credential template; LOW — an unused `argocd_project_name` default variable; LOW — inconsistent `/tmp` cleanup | `7fb4756` (implementation and all six organic fixes); `aae53bb` (Jinja-quoting fix, dead-variable removal, temp-cleanup consistency); `ed366ea` (root-from-main git-show sourcing plus its own follow-on git-auth and AppProject server-side-apply fixes, found while proving the corrected sourcing live) |

**Attacks attempted:** the RBAC-matrix test (EG52) was itself an attack on
the AppProject's policy — attempting `sync` and `delete` with a token
scoped only to `get`. The first attempt succeeded (an accidental,
disclosed incident) because the test harness itself was compromised by a
stale CLI login context, not because the policy was wrong; the corrected
retest, run against an isolated CLI config with `--core` explicitly
disabled, confirmed the policy denies both actions with an explicit
`PermissionDenied` naming the exact subject/action/resource. The drift test
(EG56) attacked the AppProject's actual GitOps ownership directly — a raw
`kubectl patch` against a live, supposedly-Argo-managed object — and
confirmed `selfHeal` reverts it without any operator intervention.

**Tracked exceptions:** one. `ARGOCD_REPO_PAT`'s over-broad scope is not
fixed in this gate; it is disclosed in full (`pat-scope-finding.txt`) and
recorded as an explicit, operator-directed deviation from the plan's own
stop-condition rule (see the deviation note at the top of this record).
Recommended follow-up: mint a fine-grained, read-only-scoped PAT and swap it
into the Secret; consider revoking the current broad-scope token now that
it has been deployed to a workload identity.

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-10-argocd-handover`
  (`7fb4756`, `aae53bb`, `ed366ea`), merged to `main` via PR #15 and #16.
- **Idempotent:** a full playbook rerun against the final merged `main`
  reports `changed=0` for every task except the by-design write-then-delete
  scratch-file steps (the repo-credential render/remove, the RBAC overlay
  render/remove, the `origin/main` fetch/render/remove-scratch steps, and
  the two copy-to-bootstrap-server steps whose source is one of those
  always-freshly-rendered files) — none of which touch k3s, Cilium, CoreDNS,
  kube-vip or storage services, and none of which restart anything.
- **Repeatable:** the role reruns cleanly from a fresh converge; the one
  manual step (applying the AppProject/root Application) is itself
  automated by the role, sourced from `origin/main` rather than a
  hand-maintained local checkout, so a different operator on a different
  control node reaches the same state.

## 8. KNOWN LIMITATIONS

- **`ARGOCD_REPO_PAT` is not read-only.** The single largest limitation of
  this record — see the Stop Condition deviation note, `pat-scope-finding.txt`,
  and the tracked exception in §7.2. This is a real, live security gap in
  the deployed credential, explicitly accepted by the repository owner
  rather than hidden.
- **No CI-time enforcement of the Cilium/CoreDNS ownership boundary.**
  `docs/security/cilium-coredns-ownership.md` documents the rule; nothing
  currently rejects a PR that adds a `gitops/infrastructure/cilium/` path.
- **Argo CD's UI/API is not exposed via Ingress.** All verification in this
  gate used `--core` mode or a manually-managed `kubectl port-forward`.
  Routine future access will need one or the other until an Ingress exists.
- **The RBAC-matrix evidence required a corrected second attempt** after a
  disclosed testing-harness bug caused a real (remediated) production
  incident — see `c1-rbac-matrix.txt` for the full account. The AppProject
  policy itself is proven correct only by the corrected run.
- **`clusterResourceWhitelist` currently allows only `Namespace`.** Any
  future `gitops/**` manifest needing a different cluster-scoped kind (a
  CRD, a ClusterRole, etc.) will need this list extended explicitly — by
  design, not an oversight.
- **Verifier independence is Tier 1 only**, for a gate CLAUDE.md §12
  classifies high-risk (installing Argo CD's CRDs/operators onto the live
  production control plane) — no Tier 2/external grader obtained,
  continuing the pattern accepted at Gates 0-9.
