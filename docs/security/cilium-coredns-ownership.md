# Cilium and CoreDNS ownership

Closes part of Gate 10's End State — "Cilium and CoreDNS ownership is
singular and documented." Argo CD's app-of-apps root
(`gitops/bootstrap/root-application.yaml`) now recurses the whole `gitops/`
tree, so anything placed under it becomes Argo-managed automatically. Cilium
and CoreDNS are deliberately never placed there: both are cluster
bootstrap-path components (CoreDNS resolves in-cluster names Argo CD itself
needs; Cilium provides the pod network Argo CD's own pods run on), so both
stay owned by the layer that exists before Argo CD does.

## Cilium

- **Owner:** Ansible (`roles/cilium`), via the pinned `cilium` CLI's own
  Helm-based install (`cilium install --version {{ cilium_version }} ...`).
- **Verified live** (2026-09-15, target `kube-system` UID
  `d7d8a462-c503-49ed-a1e0-899f372f9465`): the `cilium` DaemonSet carries
  `app.kubernetes.io/managed-by: Helm`, and six
  `sh.helm.release.v1.cilium.v{1..6}` Secrets exist in `kube-system` — all
  from `roles/cilium`'s own installs/upgrades, none from an Argo Application
  or a second Helm release history. No Argo `Application` in the cluster
  targets `kube-system` (`kubectl -n argocd get application` shows only
  `root`, `spec.destination.namespace: argocd`).
- **Never** add a `gitops/**` Application targeting Cilium. Doing so would
  create a second Helm owner racing the Ansible-driven CLI (CLAUDE.md §12/§15
  and this gate's own stop condition: "duplicate ownership").

## CoreDNS

- **Owner:** k3s itself, as a bundled addon deployed through k3s's internal
  manifest-deploy controller — driven by `roles/k3s-server`'s startup flags,
  not a Helm release and not `kubectl apply`.
- **Verified live** (same target, same date): the `coredns` Deployment in
  `kube-system` carries `objectset.rio.cattle.io/hash` (k3s's own embedded
  addon-tracking label), not a Helm release label. `k3s kubectl -n kube-system
  get secret -l owner=helm` lists only the Cilium releases above — nothing
  named `coredns`.
- **Never** add a `gitops/**` Application or a separate Helm chart for
  CoreDNS. k3s reprovisions its bundled CoreDNS deployment from its own
  embedded manifest on every server (re)start; an externally GitOps-managed
  CoreDNS would fight that reconciliation on every k3s restart, not just at
  apply time.

## Why this matters for Gate 10's stop condition

"Duplicate ownership" (Gate 10's stop condition) is a live risk specifically
because `root`'s `directory.recurse: true` (gitops/bootstrap/root-application.yaml)
picks up *anything* placed under `gitops/`, with no per-file allow-list. This
document is the enforcement mechanism: reviewers checking a future PR that adds
a `gitops/infrastructure/cilium/` or `gitops/infrastructure/coredns/` path
should treat it as a stop-condition violation, not a routine addition, unless
this document is updated first with an explicit, reasoned ownership transfer
(including how the pre-existing Ansible/Helm or k3s-native state gets
decommissioned without a gap).

## Known limitations

This documents the ownership boundary and its current live state; it is not
itself an enforcement mechanism (nothing currently rejects a PR that adds a
`gitops/infrastructure/cilium/` path at CI time). Automated enforcement is
out of scope for Gate 10.
