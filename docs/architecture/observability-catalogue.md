# Observability catalogue — dashboards, recording rules and alerts

**Status:** Target state. Not a plan amendment, not a gate requirement.
**Relationship to the plan:** Gate 11's own acceptance evidence names six alert classes (node, etcd snapshot, disk, Cilium, DNS, Argo reconciliation). Those are built and live. Everything below is the *destination* the observability stack grows toward as later gates create the services it observes. Nothing here blocks Gate 11, and nothing here should be built ahead of the workload it monitors.

**Architecture (already live, no change proposed):**

```text
vmagent → VictoriaMetrics → Grafana
                ↓
             vmalert → Alertmanager

Logs         → Fluent Bit → Loki
Network flow → Cilium Hubble
```

`vmalert` is the single authoritative rule evaluator. Grafana is presentation only — no Grafana-managed alert rules, so there is exactly one place a rule can live and one place an alert can come from.

---

## 1. Corrections applied to the source proposal

This catalogue derives from a proposed 22-dashboard inventory. Three corrections were applied before recording it, because each would otherwise have propagated into manifests:

| Source said | Correct for this platform | Why it matters |
|---|---|---|
| Backups to **GCS**; "MinIO-to-GCS replication lag", "GCS authentication failure" | **Backblaze B2** | There is no GCS in this stack. The plan was amended Wasabi → B2; the live bucket is `veridex-etcd-backup`. B2 has behaviours GCS does not: Object Lock two-phase activation, the 3× free egress allowance, and the `Content-MD5`/`x-amz-checksum-` requirement that already made k3s's native uploader unusable at Gate 9. |
| `metrics-server` for workload metrics | **kubelet + cAdvisor via vmagent** | metrics-server is not installed; `kubectl top` fails. Container CPU/memory come from the cAdvisor and kubelet scrape jobs through the authenticated API-server node proxy. |
| **Promtail** for log shipping | **Fluent Bit** | Fluent Bit is what runs, as a DaemonSet on all five nodes. |

One further note carried forward: do not hard-code the source platform's Argo CD Application count (78) as the expected value. The netcup expected count must come from its own inventory.

---

## 2. Measured metric availability — 2026-09-15

`VERIFIED` live against VictoriaMetrics (1,647 metric families present). This is what determines which dashboards can be built today versus which are waiting on something.

| Metric family | Count | Source |
|---|---:|---|
| `node_*` | 269 | node-exporter, 5/5 targets up |
| `vm*_*` (vm, vmagent, vmalert) | 376 | stack self-scrape |
| `apiserver_*` | 156 | API server via kubelet job |
| `kubelet_*` | 114 | kubelet, 5/5 |
| `kube_*` | 105 | kube-state-metrics |
| `container_*` | 72 | cAdvisor, 5/5 |
| `scheduler_*` | 45 | scheduler |
| `argocd_*` | 40 | argocd-metrics |
| `coredns_*` | 37 | CoreDNS, 2/2 |
| `k3s_*` | 24 | k3s |

**Confirmed absent, with the fix each needs:**

| Absent | Consequence | Fix |
|---|---|---|
| etcd **server** metrics (`etcd_server_has_leader`, `etcd_disk_wal_fsync_duration_seconds`) | D04's entire etcd half — quorum, leader changes, WAL fsync latency, DB quota — cannot be built. The 8 `etcd_*` families present are the *API server's client-side* view, not the etcd server's own. | k3s must expose them (`--etcd-expose-metrics`), then add a scrape job. Owning layer: Ansible (`roles/k3s-server`). This is a real gap for Gate 4's subject matter. |
| `cilium_*` (agent metrics) | D05 Cilium cannot be built. Cilium alerting currently infers agent health from kube-state-metrics pod readiness instead. | `--set prometheus.enabled=true` on the Cilium Helm values, via `roles/cilium`. Deliberately not done during Gate 11 to avoid a second Cilium change after the hubble-relay incident. |
| `hubble_*` (flow metrics) | No flow-level dashboards or drop analysis. | Requires hubble-relay healthy plus `--set hubble.metrics.enabled`. hubble-relay is currently unhealthy (see Gate 11 known limitations). |
| `alertmanager_*`, `loki_*`, `grafana_*` | The stack could not monitor two of its own components. | **Fixed** — scrape jobs added to vmagent. |

---

## 3. Dashboard inventory, mapped to the gate that creates its subject

Priority is the source proposal's. **Build gate** is the gate at which the observed service first exists — a dashboard should ship with its workload, not before.

| ID | Dashboard | Build gate | Buildable today | Notes |
|---|---|---|---|---|
| D01 | Platform Executive Overview | Gate 11 partial, completes ~Gate 15 | Partial | Top-level tiles exist for nodes/Argo/alerts; document-pipeline and HITL tiles wait on the services. |
| D02 | Nodes and Capacity | **Gate 11** | **Yes** | `node_*` fully present. |
| D03 | Kubernetes Workloads and Scheduling | **Gate 11** | **Yes** | kube-state-metrics + cAdvisor present. |
| D04 | K3s Control Plane and etcd | **Gate 11** (API/scheduler) / gap (etcd) | **Partial** | API server and scheduler yes; etcd half blocked, see §2. |
| D05 | Cilium and Hubble Networking | Gate 11 → completes at Gate 30 | **No** | Needs Cilium/Hubble metrics enabled. Full policy-verdict analysis belongs with the Gate 29/30 network-policy programme. |
| D06 | Traefik Ingress and Certificates | Gate 11 (Traefik is live) | **Partial** | Metrics and alerting are in place for both halves; dashboards are not. Traefik is scraped via its `traefik-metrics` ClusterIP (the "not yet scraped" note here was stale). cert-manager v1.21.2 is deployed and scraped at `cert-manager.cert-manager.svc:9402`, with alerts for not-Ready, expiry inside 21 days, renewal overdue, and metrics-absent. What remains for **Yes** is the Grafana panels themselves, plus per-certificate data — certificate metrics exist only once Certificate objects do, which arrives with Phase 3 of the Public TLS plan. |
| D07 | Longhorn Storage | **Gate 12** | No | Longhorn does not exist. |
| D08 | CloudNativePG PostgreSQL | **Gate 14** | No | |
| D09 | Backup and Disaster Recovery (**B2**, not GCS) | Gate 8/9 partial → Gate 17 | **Partial** | etcd snapshot freshness is live now via the textfile metric. Remaining producers (CNPG, MinIO, Longhorn, audit exporter) arrive with their gates; Gate 17 proves the matrix. |
| D10 | MinIO Object Storage | **Gate 13** | No | |
| D11 | NATS and JetStream | **Gate 14** | No | Include the exclusive-consumer/duplicate-ownership panel called for in the source. |
| D12 | Temporal Workflows and Workers | **Gate 14** | No | Schedule-to-start latency is the key capacity signal. |
| D13 | Search and Index Stores | Post-Gate-15 | No | Meilisearch/Qdrant/Memgraph. |
| D14 | Document Processing Pipeline | Post-Gate-15 | No | The central operational dashboard once applications run. |
| D15 | API and Microservice Health | Post-Gate-15 | No | Requires the RED contract in §5 to be implemented by each service. |
| D16 | Authentication and Tenant Security | Gate 15, tenant model at **Gate 35** | No | Cross-tenant assertions depend on Gate 35's declared isolation mechanism. |
| D17 | HITL and Processing Authorization | Post-Gate-15 | No | |
| D18 | RAG LLM and Model Performance | Post-Gate-15 | No | |
| D19 | Tenant Usage and SaaS Capacity | Post-Gate-15, needs **Gate 35** | No | Use PostgreSQL rollups, not per-tenant metric series. |
| D20 | Argo CD and GitOps | **Gate 11** | **Yes** | `argocd_*` present. |
| D21 | Observability Stack Health | **Gate 11** | **Yes** | Alertmanager/Loki/Grafana scrapes now added. |
| D22 | Resource Efficiency and Cost | **Gate 11** foundation, matures later | **Partial** | Recording rules and the capacity dashboard are live; cost-per-document waits on the pipeline. |

**Buildable now: D02, D03, D20, D21 in full; D04, D22 in part.** Everything else is gated on a service that does not exist, and building it early produces permanently empty panels — which erodes trust in the dashboards that do carry signal.

---

## 4. Metric-label policy — adopt immediately

Cardinality mistakes are cheap to avoid and expensive to retrofit, because the damage is already in storage by the time it is noticed. This applies to every service built from Gate 14 onward, and to any exporter added before then.

**Allowed (low cardinality, bounded set):**
`cluster`, `environment`, `namespace`, `service`, `component`, `route_template`, `method`, `status_class`, `outcome`, `stage`, `gate`, `decision`, `risk_band`, `provider`, `model`, `version`, `queue`, `priority`, `node`

**Prohibited as metric labels — unbounded or sensitive:**
document ID, job ID, workflow ID, request ID, user ID, email address, full tenant UUID, filename, object-storage key, raw HTTP path, search query, prompt or generated response, IP address, exception message.

These belong in **structured Loki logs**, traces, or audit records — where access can be controlled and retention bounded — never in a metric label.

Two rules that follow from this:
- Use **route templates** (`/documents/{document_id}`), never raw URLs. A UUID-bearing path creates one series per document.
- For tenant reporting, prefer PostgreSQL rollup queries over a permanent metric series per tenant.

---

## 5. Standard service metric contract

Every service built from Gate 14 onward should expose the same shape, so dashboards and alerts generalise rather than being hand-written per service:

```text
http_server_requests_total{service, route_template, method, status_class}
http_server_request_duration_seconds{service, route_template, method}
http_server_in_flight_requests{service}
service_dependency_requests_total{service, dependency, outcome}
service_dependency_duration_seconds{service, dependency}
service_build_info{service, version, commit}
```

---

## 6. Recording-rule families

Live today are the capacity family (container CPU/throttling, memory working set/RSS, namespace requests/limits, PVC used/capacity/requested). The remainder arrive with their subjects:

```text
cluster:node_cpu_utilization:ratio          cluster:cpu_requests_utilization:ratio
cluster:node_memory_utilization:ratio       cluster:memory_requests_utilization:ratio
service:http_requests:rate5m                service:http_error_ratio:rate5m
service:http_duration:p95_5m                service:http_duration:p99_5m
dip:documents_processed:rate1h              dip:document_failure_ratio:rate1h
dip:document_duration:p95_1h                dip:stage_backlog
dip:stage_oldest_age_seconds                dip:hitl_pending_by_gate
dip:hitl_sla_risk_by_gate                   dip:authorization_decision_ratio
dip:authorization_shadow_disagreement_ratio dip:search_index_consistency_ratio
dip:search_duration:p95_5m                  dip:rag_duration:p95_5m
dip:llm_error_ratio:rate5m                  storage:capacity_utilization:ratio
backup:recovery_point_age_seconds           platform:availability:ratio30d
```

**Constraint:** avoid chaining a recording rule onto another rule's output within the same evaluation cycle. vmalert executes a group's rules sequentially but persists results asynchronously, so a dependent rule can evaluate against stale or missing data. Put dependencies in separate groups with an interval gap, or compute from raw series.

---

## 7. Severity model and routing

| Severity | Meaning | Delivery |
|---|---|---|
| **P0** | Active data loss, tenant boundary breach, total outage, quorum loss | Immediate page |
| **P1** | Major degradation likely to breach an SLO | Immediate operational channel |
| **P2** | Capacity, backup or reliability risk needing same-day action | Operations channel |
| **P3** | Change, unusual event, or optimisation opportunity | Dashboard/ticket only |

**P0 examples:** cross-tenant access succeeds; PostgreSQL has no writable primary; etcd quorum lost; MinIO below write quorum; confirmed corruption; a required backup proven unrecoverable; audit-chain verification fails.

**P1 examples:** public API unavailable; a required service down; Longhorn volume faulted; JetStream quorum lost; Temporal queue with backlog and zero pollers; pipeline stopped; authentication or revocation enforcement unavailable.

**P2 examples:** capacity above warning; a single missed backup; index lag; certificate nearing expiry; elevated latency; Application OutOfSync; Longhorn volume degraded.

Cost and efficiency findings (D22) should create weekly review items, never pages.

**Current limitation:** Alertmanager has no external notification channel — no Slack, email or PagerDuty credential is approved or configured. "Delivery" above is aspirational until one exists; today a firing alert is visible only in Alertmanager's own API and UI. Wiring a real receiver needs its own credential and authorization.

---

## 8. Dashboard standards

Every operational dashboard carries: owner, purpose, last-reviewed date, runbook link, threshold/SLO rationale, and selectors for namespace/service/version. Metric panels should link to the corresponding Loki query so a spike leads directly to its logs.

Refresh intervals: incident dashboards 15–30s; platform overview 30s; application dashboards 30–60s; capacity and cost 5–15m.

---

## 9. Known gaps this catalogue does not close

1. **etcd server metrics are not collected** (§2). The platform's most critical stateful component is observable only through the API server's client-side view. Fixing it is an Ansible change to `roles/k3s-server` plus a scrape job.
2. **Cilium and Hubble metrics are not collected** (§2), so network observability rests on pod-readiness inference.
3. **Traefik is not scraped**, despite being live and serving Argo CD — D06 cannot be built without a metrics entrypoint.
4. **No external alert delivery** (§7).
5. **Loki and VictoriaMetrics retention are node-local hostPath** with no replication until Gate 12 provides a real StorageClass; losing that node loses the history these dashboards depend on.
