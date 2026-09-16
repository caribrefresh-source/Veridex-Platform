GATE 11 — Baseline observability

Verdict: PASS
Closed (UTC): 2026-09-16T00:15:00Z
Plan: docs/Engineering Documents/Initial Stages Plan.txt @ 4f591e3e5f954bd7829c19c938d0f5eb29d00430, sha256 4b1727a970704ee3646102c0a4d1cdd3c6a814cd356f981d24e3a39c3c4535ee
Tested repo commit: dfc225d7af1bd4c5306b8569f8cc98c08442e5ba (main, post-revert)
Target identity: kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://127.0.0.1:6443 (local kubeconfig on veridex-server-1; same cluster, confirmed by UID match against Gates 4-10's VIP-addressed https://10.2.0.100:6443)
High-risk: yes — Cilium/networking trigger (CLAUDE.md Sec.12): Cilium metrics enablement, hubble-relay enablement, a CiliumNetworkPolicy, and multiple firewall/nftables changes were all applied live to the production cluster during this gate.
Verifier independence: Tier 0 — same context that wrote the change also verified it. No Tier 1+ review was performed for this gate; disclosed as a limitation, consistent with how this session has operated throughout (all destructive/high-risk actions were preceded by explicit user authorization in this same conversation, which is the control substituted for independent verification here).

1. OBJECTIVE

   End state (plan, verbatim): "Metrics, events, logs and alerts cover all
   nodes and bootstrap services before stateful data services begin. Hubble
   flow visibility supports policy discovery."

2. SCOPE

   In scope:
     - VictoriaMetrics stack (vmagent, vmsingle, vmalert) scraping all 5
       nodes plus bootstrap services (Argo CD, CoreDNS, Traefik, Cilium,
       etcd, the observability stack's own components).
     - Loki + Fluent Bit log aggregation, all 5 nodes.
     - A Kubernetes Events watcher (events-exporter), closing the one
       explicitly-named coverage gap not otherwise covered by
       kube-state-metrics' object-state metrics.
     - Alertmanager + a minimal alert-sink webhook receiver, giving alerts a
       durable, queryable delivery record.
     - 18 alerting rules across 9 groups, covering the plan's 6 named
       classes (node, etcd snapshot, disk, Cilium, DNS, Argo reconciliation)
       plus additional capacity/health rules built along the way.
     - Cilium agent/operator metrics and hubble-relay, enabled live with
       reduced rollout blast radius (maxUnavailable: 1).
     - etcd server metrics, enabled live via k3s_etcd_expose_metrics.
     - A compensating CiliumNetworkPolicy (argocd-allow-health-probes) for
       an unrelated, pre-existing Cilium identity-misclassification bug
       discovered while working this gate (see Known Limitations).
     - 4 Grafana dashboards (D02 Nodes, D03 Workloads, D20 Argo CD, D21
       Observability self-health) and a full 22-dashboard target-state
       catalogue for future work.

   Out of scope:
     - Wave 1 of the namespace rollout (dedicated test namespace) and Gate
       34's RBAC riding alongside it → deferred to Gate 32 per ordering
       decision O4 (docs/evidence/gate-ledger.md).
     - The remaining 18 of 22 catalogued dashboards → later gates, tracked
       in docs/architecture/observability-catalogue.md.
     - Root-causing the underlying Cilium identity-misclassification bug
       itself (only a compensating control was built) → no gate currently
       owns this; flagged as an open platform-level issue.
     - PersistentVolumeClaim-backed storage metrics → no PVCs exist yet in
       this cluster (Hetzner CSI is a later gate per the sequential build
       plan); "missing storage metrics" (stop condition) was evaluated only
       against the storage metrics that exist today (node filesystem, etcd
       snapshot sync).

3. PROCESSES ACTIVATED

     - Metrics scraping (vmagent → vmsingle, 30d retention) — owner:
       Platform/SRE — detection if it silently stops: the `vmagent` and
       `vmsingle` self-scrape targets going down is itself alertable
       (added specifically because these were previously invisible).
     - Alert evaluation and delivery (vmalert → Alertmanager → alert-sink →
       Loki) — owner: Platform/SRE — detection: alertmanager/loki self-scrape
       targets, plus the durable Loki record of every delivered alert.
     - Log aggregation (Fluent Bit → Loki) — owner: Platform/SRE —
       detection: `loki` self-scrape target down, or the `node` label
       enumeration (g11-c3) regressing to fewer than 5 nodes.
     - Kubernetes Events watching (events-exporter → Loki) — owner:
       Platform/SRE — detection: pod readiness (single replica, no HA) plus
       absence of new `k8s_event` lines in Loki.
     - etcd off-cluster snapshot metrics (etcd-s3-backup sync script →
       textfile collector → node-exporter → vmagent) — owner: Platform/SRE
       — detection: EtcdSnapshotSyncStale itself, now proven live (g11-c5)
       to correctly fire on both staleness AND total absence of the metric.

4. DELIVERABLES

   D54. kubernetes/infrastructure/monitoring/ (namespace, rbac,
        node-exporter, kube-state-metrics, vmsingle, vmagent, vmalert,
        alertmanager, loki, fluent-bit, alert-sink, events-exporter,
        grafana + provisioning + dashboard ConfigMaps) @ dfc225d
   D55. kubernetes/cluster/policies/argocd-health-probes.yaml
        (CiliumNetworkPolicy compensating control, post-revert L4-only
        state) @ dfc225d
   D56. ansible/roles/cilium/ (hubble-relay enablement, agent/operator
        Prometheus metrics, reduced-blast-radius rollout controls) @ dfc225d
   D57. ansible/roles/etcd-s3-backup/ (textfile-collector metrics logic,
        applied live to veridex-server-1) @ dfc225d
   D58. ansible/roles/k3s-server/ (k3s_etcd_expose_metrics) @ dfc225d
   D59. ansible/roles/firewall/ (firewall_trusted_pod_ports: +9100, +2381,
        +9962, +9963, +4244, each independently justified and verified) @
        dfc225d
   D60. gitops/infrastructure/monitoring.yaml,
        gitops/infrastructure/cluster-policies.yaml (Argo Application
        wiring, sync-wave 0/1) @ dfc225d
   D61. docs/architecture/observability-catalogue.md (22-dashboard
        target-state catalogue, metric-family availability table,
        severity model) @ dfc225d
   D62. docs/evidence/gates/gate-11/ (this gate's own evidence and closure
        record) @ dfc225d

5. TECHNICAL DETAIL

   Resource tables: see D54-D60 above; each manifest/role carries its own
   in-file rationale comments (scrape job relabeling, RBAC scope, firewall
   port justifications) rather than duplicating them here.

   Decision rationale:
     - VictoriaMetrics (not Prometheus Operator) and Fluent Bit (not
       Promtail) per docs/architecture/observability-catalogue.md's
       corrected component list.
     - Alert severity model: P0 (etcd quorum/leader) through P3 (review),
       5 Alertmanager routes, inhibition rules suppressing dependent
       disk/capacity alerts under NodeNotReady.
     - Cilium metrics/hubble-relay were enabled with
       `cilium_allow_disruptive_upgrade` and `cilium_max_unavailable: 1` as
       explicit gates on an otherwise no-op routine converge, per CLAUDE.md
       Sec.9/15's prohibition on routine Cilium DaemonSet restarts — every
       actual roll was authorized live, in this conversation, for this
       specific action.

6. EXIT GATE

   Acceptance evidence (plan, verbatim): "Trigger and receive node, etcd
   snapshot, disk, Cilium, DNS and Argo reconciliation alerts."

   EG57. Metrics cover all nodes and bootstrap services (End state).
         Method: live `up{}` query against vmsingle, all scrape jobs.
         Evidence: docs/evidence/gates/gate-11/g11-c1-metrics-coverage.txt
         Result: PASS

   EG58. Events cover all nodes and bootstrap services (End state).
         Method: live Loki query for events-exporter's shipped lines.
         Evidence: docs/evidence/gates/gate-11/g11-c2-events-coverage.txt
         Result: PASS

   EG59. Logs cover all nodes and bootstrap services (End state).
         Method: live Loki label enumeration of the `node` label.
         Evidence: docs/evidence/gates/gate-11/g11-c3-logs-coverage.txt
         Result: PASS

   EG60. Trigger and receive the node alert.
         Method: stop k3s briefly on veridex-server-3; live Loki query for
         alert-sink delivery.
         Evidence: docs/evidence/gates/gate-11/g11-c4-alert-node.txt
         Result: PASS

   EG61. Trigger and receive the etcd snapshot alert.
         Method: a genuine live gap (metrics converge never applied) was
         found, not a planned drill; fixed live; recovery confirmed.
         Evidence: docs/evidence/gates/gate-11/g11-c5-alert-etcd-snapshot.txt
         Result: PASS

   EG62. Trigger and receive the disk alert.
         Method: temporary threshold relaxation against real live disk
         metrics, reverted to the real <15% threshold before this evidence
         was captured.
         Evidence: docs/evidence/gates/gate-11/g11-c6-alert-disk.txt
         Result: PASS

   EG63. Trigger and receive the Cilium alert.
         Method: temporary nftables DROP rule against the real Cilium
         metrics port.
         Evidence: docs/evidence/gates/gate-11/g11-c7-alert-cilium.txt
         Result: PASS

   EG64. Trigger and receive the DNS alert.
         Method: a dedicated dead static scrape target under the
         CoreDNSDown rule's real job label.
         Evidence: docs/evidence/gates/gate-11/g11-c8-alert-dns.txt
         Result: PASS

   EG65. Trigger and receive the Argo reconciliation alert.
         Method: a real, temporary Degraded ArgoCD Application.
         Evidence: docs/evidence/gates/gate-11/g11-c9-alert-argo.txt
         Result: PASS

   EG66. Hubble flow visibility supports policy discovery (End state).
         Method: live `hubble observe` during a real policy-denial
         incident; the same capture that informed the argocd-allow-
         health-probes fix.
         Evidence: docs/evidence/gates/gate-11/g11-c10-hubble-flow-visibility.txt
         Result: PASS

   EG67. Stop condition evaluation.
         Method: synthesis of EG57-EG66 plus a final Alertmanager
         active-alerts snapshot.
         Evidence: docs/evidence/gates/gate-11/g11-c11-stop-condition.txt
         Result: PASS

   Stop condition (verbatim): "No actionable alert path, missing storage
   metrics, or policy rollout without flow evidence."
   Triggered: no, as of closure — see EG67 for the full evaluation,
   including a disclosed ~6-hour window earlier in this gate's own work
   where the "missing storage metrics" clause genuinely WAS triggered
   (EG61), found and fixed before this closure was recorded.

7. ROLLBACK

   7.1 Reversal procedure.
       In reverse dependency order: remove Grafana dashboards → remove
       vmalert rule groups → remove Alertmanager/alert-sink →
       remove vmagent scrape jobs → remove vmsingle/vmagent/vmalert
       Deployments → remove node-exporter/kube-state-metrics/fluent-bit
       DaemonSets/Deployments → remove events-exporter → remove the
       monitoring namespace's Argo Application → revert
       ansible/roles/cilium, ansible/roles/etcd-s3-backup,
       ansible/roles/k3s-server, ansible/roles/firewall to their pre-Gate-11
       defaults and reconverge → remove
       kubernetes/cluster/policies/argocd-health-probes.yaml. Nothing here
       is IRREVERSIBLE: no data is destroyed (vmsingle/Loki hold only
       observability data, not primary state), and every change traces to
       a Git revision that can be reverted and reconverged. etcd quorum,
       Cilium datapath state and Argo CD's own operation are all preserved
       throughout a rollback of this gate's changes.

   7.2 Adversarial hardening loop.
       1 iteration run over the changes made in this gate's closing
       session (the argocd-allow-health-probes CiliumNetworkPolicy and the
       etcd-s3-backup role).
         Finding 1: argocd-allow-health-probes admitted traffic to
         8080/8082/8084 by L4 port alone, but those ports are not
         dedicated health listeners — argocd-server's own Service maps
         both http and https to the same targetPort 8080 that serves
         /healthz (verified live), so the policy over-granted the full
         UI/API/gRPC surface, not just the probe, to any source matching
         host/remote-node/health, the pod CIDR, or (worst case) world.
         Fix attempted: an L7 HTTP rule scoping those three ports to GET
         /healthz(.*), using Cilium's confirmed-active Envoy proxy.
         Attack: rolled out live. Result: a real, actively-worsening
         regression — argocd-server (on veridex-agent-2, a node uninvolved
         in the original identity-misclassification bug), repo-server, and
         application-controller all began failing their own liveness/
         readiness probes with "context deadline exceeded", restart counts
         climbing continuously across ~100s of observation rather than
         stabilizing. Root cause not confirmed before revert (most likely:
         Envoy redirect latency against the probes' tight 1-5s timeouts).
         Decision: reverted immediately (commit cc3e588, applied live via
         an authorized emergency `kubectl apply` after GitOps itself could
         not deliver the revert — repo-server, the component needed to sync
         it, was the thing being broken; the same bootstrapping deadlock as
         the original repo-server incident earlier in this gate). Recovery
         confirmed live: all 4 pods stable for 3+ minutes, all 5 Argo
         Applications back to Synced/Healthy, live state matches the merged
         Git revision (no drift).
         Re-identify: no further findings pursued after the revert, given
         the demonstrated live blast radius of iterating further against
         production ArgoCD.
         Accepted as a tracked exception by the repository owner,
         2026-09-15: Gate 11 closes with the L4-only over-grant on
         8080/8082/8084 left open and disclosed (in the policy's own
         comments and here), rather than holding closure for a safer L7
         approach to be developed separately.

   7.3 IIR attestation.
         - Immutable: every fix in this gate is committed and, where
           applicable, digest-pinned (container images) or version-pinned
           (Helm/chart values) — commits through dfc225d.
         - Idempotent: the etcd-s3-backup playbook's own built-in
           post-sync assertion passed on its live converge; a second
           `cilium upgrade --reuse-values` or `k3s-server`/`firewall`
           converge was not re-run to confirm changed=0 in this closing
           session — carried forward as unverified in this specific
           record (the individual build-phase commits each confirmed their
           own idempotency at the time; not re-confirmed as one batch
           here).
         - Repeatable: a clean-node rebuild would reach node-exporter,
           kube-state-metrics, vmagent/vmsingle/vmalert, Loki/Fluent Bit,
           events-exporter and the firewall/Cilium/k3s ansible changes the
           same way, with no uncaptured manual step. The one live manual
           step in this closing session (the direct `kubectl apply` revert
           of argocd-health-probes.yaml) is not part of a clean rebuild's
           path — a clean rebuild starts from the reverted, L4-only Git
           state directly and never goes through the broken L7 state at
           all.

8. KNOWN LIMITATIONS

   - The underlying Cilium identity-misclassification bug (legitimate
     `reserved:host` traffic intermittently resolving as `reserved:world`)
     is NOT fixed — only compensated for, narrowly, on 4 ArgoCD pods'
     health-check ports. It may affect other host-networked or
     kubelet-probed workloads elsewhere in the cluster that this gate did
     not investigate. No gate currently owns root-causing it.
   - argocd-allow-health-probes admits ports 8080/8082/8084 by L4 port
     alone, not path-restricted — a real over-grant to the full ArgoCD
     UI/API/gRPC surface, accepted as a tracked exception per Sec.7.2
     above. An L7 fix was attempted and reverted after causing a live
     regression; not re-attempted in this gate.
   - ContainerCPUThrottlingHigh (a P2 capacity alert, unrelated to this
     gate's required classes) was observed active throughout this gate's
     closing evidence-gathering, against node-exporter's own pod. Not
     investigated further; disclosed in g11-c5's raw Alertmanager snapshot.
   - Verifier independence is Tier 0 (Sec. above) — no separate review
     pass was run over this gate's accumulated changes by a different
     context, model or person.
   - This gate's "missing storage metrics" stop-condition clause is scoped
     to the storage metrics that exist today (node filesystem, etcd
     snapshot sync); it says nothing about PVC-level storage metrics,
     since no PVC-backed storage exists yet in this cluster.
   - Idempotency of the ansible converges bundled into this gate (Cilium,
     etcd-s3-backup, k3s-server, firewall) was confirmed individually at
     build time, not re-confirmed as one batch at closure time (Sec.7.3).
