# Sequential Service Build Plan

**Status:** Corrected after 11 adversarial review iterations  
**Purpose:** Canonical, dependency-ordered GitOps build ledger for the Document Intelligence Platform  
**Evidence date:** 2026-09-15  
**Sources:** `K3s-HA/docs/operations/argocd-application-inventory.md`, `K3s-HA/eng-design/Document Intelligence Platform v4.4.docx`, repository manifests/source, and the current Kubernetes context <!-- provider-drift-ok: historical source platform comparison -->

## 1. Truth model

Never use `existing` without a qualifier. Every unit must independently record:

- **Specified:** present in the architecture.
- **Coded:** substantive source exists.
- **Declared:** GitOps manifests exist and are reachable from a parent application.
- **Reconciled:** an Argo CD `Application` exists in the target cluster.
- **Running:** desired workloads are available and Services have ready EndpointSlices.
- **Verified:** the unit-specific functional and failure tests pass with retained evidence.

Promotion is monotonic only through evidence. A unit may be coded and declared while not reconciled or running.

Current-cluster baseline: five Argo applications are visible (`cluster-namespaces`, `cluster-policies`, `monitoring`, `root`, `traefik`); only `argocd`, `monitoring`, and system namespaces exist. The older inventory's statement that 78 applications are live is historical/stale for this context and must not be used as deployment proof.

## 2. Repeatability contract

Every build unit MUST satisfy all applicable controls before promotion:

1. Desired state originates in Git; no imperative mutation is accepted as final state.
2. Git revision, chart version, CRD version, image digest, configuration checksum, and migration version are recorded.
3. Container images use immutable digests in promoted environments. Mutable tags are informational only.
4. Helm dependencies and remote manifests are pinned and integrity checked.
5. Applying or syncing the same revision twice produces no material diff and no duplicate side effect.
6. Jobs and migrations have explicit idempotency keys, advisory locks, or version guards.
7. Reconcilers use deterministic names and server-side ownership; generated values are persisted rather than regenerated on each sync.
8. Secrets are referenced by stable names and versions; plaintext never enters Git or evidence bundles.
9. Stateful changes declare backup, restore, forward-migration, and rollback/roll-forward behavior before execution.
10. Destructive schema changes use expand/migrate/contract and are not coupled to a single application rollout.
11. A failed sync can be retried safely. A successful sync followed by restart or rescheduling preserves correctness.
12. Evidence is machine-readable where possible and stored under a stable path keyed by unit, commit, cluster, and timestamp.

## 3. Standard exit gate

For each deployable unit retain:

- rendered-manifest validation and policy results;
- commit SHA and immutable artifact digests;
- Argo source revision, `Synced`, and `Healthy` evidence;
- rollout status, desired/available replicas, pod readiness and restart counts;
- ready EndpointSlices for every expected Service;
- in-cluster readiness, dependency, and negative-connectivity tests;
- structured-log query showing no unexplained startup/dependency errors;
- VictoriaMetrics scrape/query evidence and loaded alert rules;
- unit-specific happy-path, failure-path, retry, restart, and duplicate-delivery tests;
- tenant-isolation and authorization tests where applicable;
- persistence and restore evidence where applicable;
- second-sync no-diff result;
- rollback or roll-forward rehearsal result.

Argo `Synced` alone is never sufficient. A unit with no ready endpoint, such as the current `hubble-relay`, is not verified.

## 4. Canonical sequential build ledger

Each number is a promotion boundary. Components on the same number may be one atomic GitOps unit only when they share lifecycle and rollback semantics.

### Stage A — decisions and cluster substrate

1. **Baseline capture and target-context lock** — Record cluster identity, Kubernetes/K3s version, nodes, namespaces, CRDs, storage classes, Argo applications, Git revision, and existing workloads. Abort on context mismatch.
2. **Architecture reconciliation decision** — Correct the `v4.4.docx` filename/internal `v4.3` mismatch; mark the 78-application inventory as historical for the current context; select `docintel` or `data-plane` as the one canonical namespace; reconcile SOPS/age versus Sealed Secrets; document VictoriaMetrics rather than legacy Prometheus Operator ownership.
3. **Argo CD control plane** — Reconcile the existing installation; verify repository authentication, projects, health customizations, retry policy, sync windows, and controller recovery. Do not replace a working control plane.
4. **Root app-of-apps alignment** — Reconcile current names (`root`, `cluster-namespaces`, `cluster-policies`, `monitoring`, `traefik`) with repository names (`k3s-ha-root`, `infra`, `observability`, `secrets`). Migration must avoid creating two owners for one resource. <!-- provider-drift-ok: historical source platform comparison -->
5. **Namespaces and security labels** — Create the canonical application, `cnpg-system`, and required infrastructure namespaces with deterministic labels, quotas, LimitRanges, and Pod Security settings.
6. **RBAC and service accounts** — Apply least-privilege roles/bindings; prove allowed operations work and denied operations fail.
7. **Cilium core** — Reconcile CNI, VXLAN, WireGuard, MTU 1400, default-deny posture, and deterministic egress rules.
8. **Cilium Envoy and Hubble Peer** — Verify node coverage and flow visibility.
9. **Hubble Relay repair** — Restore ready endpoints before declaring network observability complete.
10. **CoreDNS** — Prove Kubernetes service discovery and allowlisted external DNS resolution.
11. **Node identity and addressing (no cloud controller)** — netcup provides no cloud controller manager, so k3s runs with `disable-cloud-controller: true` and deliberately without the external cloud-provider setting, which would leave every node tainted `uninitialized` with nothing to clear it (`ansible/roles/k3s-server/templates/config.yaml.j2`). Verify no node carries that taint, node addresses come only from the Ansible address register, and the kube-vip API VIP fails over (Gate 5). *Replaces the source platform's Hetzner CCM unit.*
12. **Longhorn and storage classes** — Longhorn is the approved block storage (gate ledger O5; Gate 12), and k3s's `local-storage` provisioner is disabled. Test dynamic provision, mount, detach, reschedule, reclaim, replica placement across distinct nodes, and retained-volume recovery. MinIO data never uses Longhorn — it runs on direct local paths so erasure coding stays its only replication layer (Gate 13). *Replaces the source platform's Hetzner CSI unit.*

### Stage B — identity, secrets, ingress, and policy

13. **cert-manager CRDs/controller** — Install CRDs before Certificate resources and verify controller recovery.
14. **Route 53 DNS-01 and the `letsencrypt-dns` issuer** — DNS authority for `veridexeai.com` is Route 53, and cert-manager's built-in Route 53 solver needs no webhook. The credential is scoped to TXT changes by `docs/security/route53-iam-policy.json` and delivered through SOPS + age (`docs/security/route53-dns01.md`). Prove DNS-01 issuance and renewal against Let's Encrypt staging before production; HTTP-01 remains prohibited. Sequenced by Stage F of the Public TLS plan. *Replaces the source platform's Hetzner DNS webhook unit.*
15. **Canonical secret controller** — Reconcile Sealed Secrets if retained. Do not operate SOPS/age and Sealed Secrets as ambiguous co-owners. Test decrypt/reseal and disaster recovery.
16. **Reflector** — Restrict reflection to explicitly approved secrets/certificates and namespaces.
17. **Vault** — If retained, define its non-overlapping role, then verify initialization, unseal, persistence, policy, backup, and restore.
18. **Vaultwarden** — Deploy only after its data ownership, TLS, backup, and recovery contract is explicit.
19. **Traefik data plane** — Reconcile the existing K3s controller and verify readiness, TLS 1.3, HSTS, redirects, and restart behavior.
20. **Traefik configuration** — Apply TLS options, middleware, rate limits, routes, and later-bindable ForwardAuth references without routing traffic to absent backends.
21. **CrowdSec** — Verify bouncer integration, controlled malicious-request blocking, logging, and false-positive recovery.
22. **KEDA control plane** — Verify operator and metrics API only; defer workload ScaledObjects until metrics exist.
23. **Headlamp** — Apply authenticated least-privilege access over valid TLS.

### Stage C — observability, audit, and generic recovery

24. **Audit policy** — Enable required Kubernetes audit events with secret/body redaction.
25. **Loki** — Establish durable log ingestion and query before application rollout.
26. **Fluent Bit audit pipeline and WORM transport foundation** — Prove delivery to Loki and the selected immutable object-storage path; WORM completeness is closed again at unit 86.
27. **VictoriaMetrics/VMSingle** — Verify durable storage, retention, restart, and query behavior.
28. **VMAgent** — Verify target discovery without Prometheus Operator CRDs.
29. **VMAlert** — Load rules and fire a controlled alert.
30. **Alertmanager and Alert Sink** — Verify routing, deduplication, inhibition, delivery, and recovery. Alert Sink is retained because it exists in the current cluster.
31. **Grafana** — Provision datasources, RBAC, and the required platform, pipeline, RAG, AI-safety, billing, backup, SLO, security, Temporal, and drift dashboards.
32. **kube-state-metrics** — Verify object-state metrics.
33. **metrics-server** — Verify node/pod resource metrics and APIService health.
34. **node-exporter** — Verify expected node coverage and host metrics.
35. **Velero CRDs** — Establish CRDs before controller and custom resources.
36. **Velero controller** — Verify backup-location access and controller recovery.
37. **Velero resources and schedules** — Test a namespace backup/restore and repository maintenance; do not claim application-consistent database recovery from Velero alone.

### Stage D — data and messaging plane

38. **CloudNativePG operator** — Install CRDs/operator and verify reconciliation before creating a database cluster.
39. **PostgreSQL CNPG cluster** — Deploy primary/standby, pooling and certificates; test replication, failover, disruption, persistence, and fencing.
40. **PostgreSQL backup/PITR** — Prove WAL archiving and point-in-time recovery. Target RPO is at most one hour.
41. **Migration Runner** — Run versioned, locked, idempotent expand migrations. A second run must be a safe no-op. Contract migrations occur only after compatible application rollout.
42. **MinIO** — Verify persistence, tenant-prefix authorization, lifecycle behavior, backup replication, and restore.
43. **NATS chart/service** — Deploy the broker with pinned version and persistence/authorization decisions.
44. **NATS supplemental manifests** — Apply streams, consumers, policies, or configuration only after the broker is ready; remove duplication between `dip-nats` and `dip-nats-manifests`.
45. **Redis** — Reconcile one canonical instance; verify TTL, eviction, memory limits, restart, and declared ephemeral recovery behavior.
46. **Temporal Server** — Verify persistence, namespaces, task dispatch, signal handling, restart recovery, and disruption behavior.
47. **Qdrant** — Verify vector CRUD, collection policy, snapshot and restore.
48. **Meilisearch** — Verify index CRUD, filtering, dump and restore.
49. **Memgraph** — Verify graph CRUD/traversal, snapshot, restore, and replay behavior.
50. **Ollama** — Treat as an optional provider. Deploy only with a selected model, immutable model provenance, resource budget, and successful inference test.

### Stage E — identity and common application contracts

51. **Auth Service** — Build/deploy `services/auth-service`; verify JWT/JWKS, expiration, JTI revocation, deny-wins RBAC, permission-cache invalidation, tenant isolation, and supported WebAuthn/SAML behavior.
52. **Traefik ForwardAuth activation** — Bind routes only after Auth Service is verified. Prove absent/expired/revoked tokens fail and trusted identity headers cannot be spoofed.
53. **Transactional Outbox contract** — Establish the shared schema/library contract, atomic write behavior, stable event IDs, ordering rules, retry semantics, lag metrics, and retention.
54. **Outbox Relay ownership decision and implementation** — Either deploy a standalone relay or formally assign relay responsibility to Temporal/domain workers. Never run two consumers with conflicting ownership. Prove at-least-once delivery plus idempotent effects.

### Stage F — intake, storage, and document processing

55. **Ingestion Service** — Verify upload validation, MIME/size policy, capacity checks, lifecycle admission, tenant isolation, quarantine, and outbox emission.
56. **ClamAV ingestion capability** — Implement as the declared sidecar/service topology; verify infected/clean samples, stale signatures, circuit-open behavior, and alerting.
57. **File Manager** — Verify MinIO access, ACL synchronization, cursor integrity, duplicate detection, reconciliation, orphan repair, custody export, restart, and tenant isolation.
58. **Preview Service** — Verify deterministic thumbnail/page rendering, object registration, authorization, retry, and malformed-document handling.
59. **Client Sync Service** — Verify resumability, idempotency, conflict rules, deletion semantics, and duplicate event handling.
60. **Notification Service** — Verify logical exactly-once effects over at-least-once delivery, templates, retry, failure isolation, and metrics.
61. **OCR Service** — Verify native/scanned inputs, layout and confidence outputs, low-confidence review routing, resource exhaustion, and malformed inputs.
62. **NLP Preprocessing Service** — Verify cleanup, NER, tagging, classification, metadata extraction, quality fixtures, model provenance, and deterministic contracts.
63. **Embedding Service** — Verify model/version provenance, dimension contract, Qdrant writes, retry/idempotency, batch limits, and drift metrics.
64. **Cross-Encoder Service** — Verify scoring, batching, model provenance, timeout, resource exhaustion, and fallback contract.
65. **Enrichment compatibility boundary** — Do not build a duplicate monolith. Mark the architecture's Enrichment Service as superseded by Preview, OCR, NLP, Embedding, and Cross-Encoder; prove every former process has exactly one owner.
66. **Temporal Workers** — Verify all declared queues, durable retries, signals, idempotent activities, replay safety, Continue-As-New, worker loss, and versioned workflow compatibility.
67. **Data Consistency Service** — Verify divergence detection/repair across stores, DLQ replay, safe reruns, GDPR verification support, and repair audit records.
68. **Marker Worker disposition gate** — It has a source directory but no normal code or deployment evidence. Classify it as required and implement it, or record a reviewed deprecation. Never silently delete or count it as built.

### Stage G — authorization, governance, and human review

69. **Processing Authorization Mode Contracts** — Version and validate schemas/contracts before deploying consumers.
70. **Processing Authorization Service** — Verify authorization decisions, tenant policy, auditability, fail-closed behavior, and contract compatibility.
71. **Processing Authorization Reconciler** — Verify deterministic drift detection, idempotent correction, concurrency control, and no oscillation.
72. **Processing Authorization Mode Service** — Confirm whether it shares the main codebase; verify mode resolution and fail-safe behavior without inventing a duplicate source project.
73. **Processing Authorization Mode Health** — Verify it reports dependency and reconciliation health rather than simple process liveness.
74. **Governance Service** — Deploy the single owning Argo application and verify governance workflow/audit behavior.
75. **Metadata Service** — Retain as a distinct workload under the Governance application; verify provenance and tenant isolation.
76. **Policy Service** — Retain as a distinct workload under the Governance application; verify deterministic deny-safe evaluation.
77. **Rule Service** — Retain under the Governance application unless an ownership ADR changes it; reconcile `services/rule-service` with that workload and avoid a second Argo owner.
78. **HITL Service** — Verify all seven gates, reviewer assignment/heartbeat, escalation, SLA metrics, mandatory gates, risk-based bypass rules, timeout recovery, and Continue-As-New integration.

### Stage H — search, LLM, and RAG

79. **Search Service** — Verify full-text/vector/graph retrieval, fusion, authorization, tenant isolation, backend degradation, and stable pagination.
80. **Search Gateway** — Verify authenticated routing, quotas, timeouts, error normalization, trace propagation, and abuse controls.
81. **LiteLLM Gateway** — Pin the third-party artifact; verify provider routing/fallback, token budgets, spend accounting, semantic caching, health isolation, and secret rotation.
82. **RAG Retriever** — Verify all three backends, per-backend circuit breakers, cache correctness, authorization filtering, and degraded operation.
83. **RAG Re-Ranker** — Verify cross-encoder ranking, batching, latency limit, deterministic fallback, and model provenance.
84. **RAG Context Builder** — Verify token budget, relevance threshold, source citations, tenant filtering, prompt-injection boundaries, and PII handling.
85. **RAG Orchestrator** — Verify end-to-end timeout, cancellation, provider failure, citations, and `X-RAG-Trace-ID`/W3C trace correlation.

### Stage I — compliance, commercial, and operational services

86. **WORM Audit Shipping completion** — Close end-to-end gap detection, chained hashes, retention lock, replay, and zero-gap evidence. This completes the transport foundation from unit 26.
87. **Webhook Delivery Service** — Planned: implement signed delivery, stable event IDs, exponential retry, endpoint isolation, idempotency, dead-letter handling, replay, and observability.
88. **Billing Service** — Planned: implement metering, Stripe webhook idempotency, quotas, immutable billing events, revenue records, reconciliation, and tenant isolation.
89. **RLHF Pipeline** — Planned: implement feedback provenance, validation, drift input, dataset versioning, retraining approval, evaluation, promotion, and rollback.
90. **Model and Embedding Drift Monitor** — Assign explicit ownership to RLHF plus model-serving services; verify scheduled baselines, thresholds, alerts, version correlation, and safe retraining triggers.
91. **Backup Orchestrator** — Planned: coordinate lock, Temporal pause/resume, CNPG backup, Temporal export, Qdrant snapshot, Meilisearch dump, Memgraph snapshot, audit shipping, cold replication, integrity checks, and safe concurrent/repeated execution.
92. **Automated Restore Validation** — Run scheduled isolated restores, schema/audit-chain validation, smoke tests, duration recording, alerting, and deterministic cleanup. Target full-platform RTO is at most 30 minutes.
93. **GDPR Deletion Orchestrator** — Assign to a versioned Temporal workflow; verify deletion across PostgreSQL, MinIO, Meilisearch, Qdrant, and Memgraph, legal-hold behavior, retries, signed per-store certificate, and SLA.
94. **Prompt-Injection Detection** — Embedded AI-safety control, not a new service unless an ADR makes it one. Verify against versioned evaluation data and the declared accuracy target.
95. **LLM Output Moderation** — Embedded control; verify unsafe-output handling, audit events, fail-safe behavior, and provider outage behavior.
96. **LLM Input/Output PII Redaction** — Embedded control; verify known PII fixtures, authorization-aware unredaction, auditability, and absence of unauthorized provider leakage.

### Stage J — scaling, exposure, and closure

97. **Workload scaling policies** — Replace empty small/medium/large overlays with measured HPA/KEDA policies only after metrics and load tests exist. Prove scale-up, stabilization, scale-down, and capacity limits.
98. **External-route activation** — Expose one verified service at a time through Traefik; test TLS, ForwardAuth, rate limits, WAF, headers, timeouts, and rollback.
99. **End-to-end document workflow** — Verify upload through processing, indexing, HITL, search/RAG, audit, notification, deletion, billing, backup, and restore with trace/evidence continuity.
100. **Orphan cleanup decision: ingress-nginx** — It is unreconciled and conflicts with the Traefik decision. Remove only through reviewed Git history after confirming no ownership/reference remains; otherwise adopt explicitly. Never deploy accidentally.
101. **Orphan cleanup decision: kube-prometheus-stack** — It is legacy and unreconciled. Remove only after proving VictoriaMetrics coverage and no remaining dependency.
102. **Production sign-off** — Require SRE, Security, Compliance, AI Ethics, and Platform Architecture evidence review. No production claim while required units remain merely declared or while cluster evidence disagrees with inventory.

## 5. Per-unit immutable evidence layout

Use a stable structure such as:

```text
evidence/<cluster-id>/<unit-number>-<unit-name>/<git-sha>/<utc-timestamp>/
  inputs.json
  rendered-manifests.sha256
  artifact-digests.json
  policy-results.json
  argocd.json
  rollout.json
  endpointslices.json
  functional-tests.xml
  failure-tests.xml
  metrics.json
  logs.json
  second-sync-diff.txt
  recovery-test.json
  verdict.json
```

Evidence is append-only. `verdict.json` identifies inputs and test outputs by digest. Re-running a build creates a new evidence run; it never overwrites an earlier result.

## 6. Build algorithm

For unit `N`:

1. Verify all declared predecessors have passing, digest-addressed verdicts.
2. Render from a pinned Git revision in a clean environment.
3. Validate schemas, policy, signatures, provenance, and dependency compatibility.
4. Reconcile through Argo CD.
5. Wait for Kubernetes runtime conditions, not elapsed time.
6. Execute positive, negative, failure, restart, duplicate, and recovery tests applicable to the unit.
7. Sync the identical revision a second time and require no material diff or duplicate side effect.
8. Store evidence and issue a pass/fail verdict.
9. On failure, preserve evidence, roll forward or back using the declared strategy, and do not advance dependent units.
10. Resume by re-evaluating actual predecessor verdicts; never rely on a manually remembered checkpoint.

This makes execution immutable in inputs and evidence, idempotent in reconciliation and side effects, and repeatable across later builds.

## 7. Prohibited shortcuts

- Treating repository presence, an Argo `Application`, or `Synced` as proof that a service works.
- Using the historical 78-application count as current-cluster evidence.
- Deploying both Traefik and orphaned ingress-nginx without an approved migration design.
- Deploying legacy kube-prometheus-stack beside the selected VictoriaMetrics stack by accident.
- Creating a monolithic Enrichment Service in addition to its five replacement services.
- Creating a second Rule Service owner outside the Governance application.
- Running two Outbox Relay owners or two secret-management ownership models ambiguously.
- Advancing past a missing EndpointSlice, failing negative test, untested restore, or mutable artifact reference.
- Using `kubectl edit`/`patch` as durable desired state.
- Deleting unresolved Marker Worker or orphaned manifests without a reviewed decision and recoverable Git history.
