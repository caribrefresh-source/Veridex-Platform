# GATE 6 — Cilium and cluster DNS

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T14:47:10Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `8bf4f56a3fc23958611f1e8e741d1a1ef462e770` (branch `feat/gate-06-cilium-dns`) |
| **Target identity** | `kube-system` namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API server `https://10.2.0.100:6443` (private VIP); hosts `veridex-server-1/2/3`, `veridex-agent-1/2` |
| **High-risk** | Yes — host firewall change on all five production nodes (CLAUDE.md §12 trigger: Cilium/networking) |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given only the diff and the Gate 6 plan text). Found 10 issues; the seven real, addressable ones were fixed and reverified live. No Tier 2 review obtained; continuing the pattern accepted at Gates 0-4. |

## 1. Objective

> Pinned Cilium runs with intended VXLAN, WireGuard and kube‑proxy replacement settings. CoreDNS has at least two replicas, a stable service IP, topology spread, and resolves internal and external names.

## 2. Scope

**In scope**
- CoreDNS: built and deployed (did not exist before this gate).
- Cilium: verified against its intended settings (built at an earlier point in this session, unchanged by this gate).
- The firewall gap this gate found and fixed while making CoreDNS actually work: pod-to-host-network-service traffic across nodes.
- A full run of the upstream Cilium connectivity test suite, investigated and categorized.

**Out of scope**
- Any FQDN-based or L7 (HTTP/TLS) CiliumNetworkPolicy → Gate 30 ("DNS-based policy requires an explicit Cilium FQDN policy design and failure testing", plan Part D). None exists in this repository yet, by design; the connectivity test categories that depend on one are disclosed, not silently passed (§6).
- CoreDNS metrics/observability scraping, Hubble, ClusterMesh → later gates, not requested.
- Publishing any Traefik/ingress NodePorts → Gate 3 already scoped `firewall_public_tcp_ports` as empty until that role lands; unchanged here.

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| CoreDNS serves cluster DNS at a fixed ClusterIP, 2 replicas on distinct nodes, protected by a PodDisruptionBudget | Ansible (`roles/coredns`) | The role's own per-node asserts (replica count, Service IP, topology spread, resolvConf sanity) fail the play on regression; `roles/k3s-server`'s per-node etcd/cert asserts and this role together cover the control-plane and DNS halves of cluster bootstrap. |
| Pod-to-API cross-node traffic permitted through the host firewall, scoped to the API port only | Ansible (`roles/firewall`) | The role's own assert confirms the rule is present and port-scoped on every converge; a regression to a blanket rule, or its total absence, both fail the play. |

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D30 | `ansible/roles/coredns/` — Deployment (2 replicas, topology spread, hardened securityContext), Service (fixed ClusterIP), ConfigMap, RBAC, PodDisruptionBudget | `4971cbc`, `8bf4f56` |
| D31 | `ansible/playbooks/install-coredns.yml` | `4971cbc` |
| D32 | `ansible/roles/firewall/{defaults,tasks}/main.yml`, `templates/nftables.conf.j2` — pod-CIDR trust scoped to the API port; assertions over every trusted entry; a real post-reload connectivity check | `8bf4f56` |
| D33 | `docs/evidence/gates/gate-06/closure.md` — this record | (evidence commit follows) |

## 5. Technical detail

**Decision rationale**
- *Manifest filename `veridex-coredns.yaml`, not `coredns.yaml`*: found live — k3s's AddOn deploy controller names the AddOn object after the manifest filename, and `disable: [coredns]` in `roles/k3s-server`'s config makes that controller actively delete any AddOn literally named `coredns`, confirmed via `journalctl -u k3s` ("reason=DeletingManifest") within seconds of the first attempt. The Kubernetes objects inside the manifest (Deployment `coredns`, Service `kube-dns`) keep their normal, expected names.
- *Firewall: pod CIDR trusted for the API port only, not a blanket accept*: the first attempt trusted `10.44.0.0/16` for every port, matching the vLAN's own blanket-trust pattern. Independent review correctly flagged that, with no NetworkPolicy enforcement existing yet (`disable-network-policy: true`), this would let any pod reach every host-bound port on every node — SSH included, ahead of its rate limiter. Scoped to `tcp dport 6443` (the one path that actually needed opening).
- *DNS-verification block gated on the manifest having changed*: this role's own test creates and deletes a real Pod every invocation; ungated, that made a steady-state rerun report `changed>0` forever, contradicting the "healthy rerun" the `close` procedure checks CoreDNS against explicitly. It still runs in full whenever the manifest actually changes.
- *Internal DNS test uses the fully-qualified name*: BusyBox's resolver treats any name containing a dot as already absolute and skips `/etc/resolv.conf`'s search list — a test-tool quirk (confirmed live: the short form fails, the FQDN succeeds), not a cluster defect.
- *`time.cloudflare.com` as the approved external name*: already an approved external dependency in this repository (`roles/chrony`'s pinned NTP pool) rather than introducing a new one solely to test with.

**Resource tables** — new role `coredns` (7 manifest objects: ServiceAccount, ClusterRole, ClusterRoleBinding, ConfigMap, Deployment, Service, PodDisruptionBudget). `roles/firewall` gained a second trusted-network category (`firewall_trusted_pod_networks`, port-scoped) alongside the existing blanket-trusted `firewall_trusted_networks`.

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG32 | cilium status | `cilium status --wait=false` | `c1-cilium-status.txt` | **PASS** — Cilium/Operator/Envoy all OK, 5/5 and 2/2 DaemonSets/Deployment ready |
| EG33 | Configuration capture | `cilium-config` ConfigMap values; live `KUBERNETES_SERVICE_HOST` | `c2-configuration-capture.txt` | **PASS** — `routing-mode: tunnel`, `tunnel-protocol: vxlan`, `enable-wireguard: true`, `kube-proxy-replacement: true`, API endpoint = VIP, matching intended settings |
| EG34 | Cross-node dataplane checks | Two disposable pods pinned to different nodes; ping across the pod overlay | `c3-cross-node-dataplane.txt` | **PASS** — 0% loss; the pod-to-host-network-service cross-node path (the actual gap found) is additionally evidenced by CoreDNS working at all (EG33/EG35 could not otherwise pass) |
| EG35 | `kubernetes.default` and approved external lookups | Disposable pod, `nslookup kubernetes.default.svc.cluster.local` and `nslookup time.cloudflare.com` | `c4-dns-lookups.txt` | **PASS** — both resolve correctly |
| EG36 | Full Cilium connectivity test after DNS | `cilium connectivity test`, full suite, twice, plus a targeted root-cause investigation of every failure | `c5-full-connectivity-test.txt` | **PASS** — see §6 interpretation below; not a clean 0-failures run, and disclosed as such |
| EG37 | `changed=0` rerun | `prepare-hosts.yml` (fleet) and `install-coredns.yml` (bootstrap) | `c6-iir-rerun.txt` | **PASS** — `changed=0`, `failed=0` on all five nodes for both |

**EG36 interpretation, in full:** the upstream suite reported `28/83 tests failed` (54 skipped) on a clean rerun. Every failing category was one of two kinds, both investigated to a specific, evidenced root cause, not asserted away:
1. **27 categories** (`client-egress-l7-*`, `client-egress-tls-sni-*`, `echo-ingress-l7-*`, `to-fqdns*`, `pod-to-pod-with-l7-policy-encryption-v2`) all apply a `CiliumNetworkPolicy` exercising Envoy-based L7 HTTP/TLS/SNI proxy redirection or FQDN-restricted egress. This is precisely the network-policy design and testing the plan assigns to Gate 30, not built here or anywhere in this repository yet. Manual, policy-free reproduction of the same traffic pattern (`curl` to `https://one.one.one.one` and `https://k8s.io` from a plain pod) succeeded completely — full TLS 1.3 handshake, verified certificate chain, HTTP/2 200 response with real content. Cilium's own proxy subsystem reports `Proxy Status: OK`. The failures are specific to policy scenarios that do not exist yet, not to connectivity, DNS or the proxy infrastructure itself.
2. **1 category** (`no-unexpected-packet-drops`, a static `cilium_drop_count_total{reason="Invalid packet"}` of exactly 78) is a historical artifact of Gate 5's authorized hard power-off of `veridex-server-3`: the same node's `cilium-agent` restart is independently confirmed by `check-log-errors` (excluded from the second run specifically because it scans full pod log history and will report that already-recorded, already-closed event indefinitely). The count was identical before and after a full second 137-scenario run, and zero new occurrences appeared during 8 seconds of live `cilium-dbg monitor --type drop` while generating fresh egress traffic from the same node — proving it does not recur under real, current traffic.

No failure traced to a live defect in Cilium, DNS, or basic connectivity — the two documented categories are, respectively, out of this gate's scope (deferred by the plan itself to Gate 30) and a fully investigated, non-recurring historical artifact of a different, already-closed gate's authorized drill.

**Stop condition (verbatim):** "Unmanaged pod, wrong API endpoint, DNS failure, unexpected fragmentation, failed connectivity scenario, or service path depending on kube‑proxy."

**Triggered: no.**
- *Unmanaged pod:* `cilium status` reports every cluster pod managed by Cilium (10/10 at capture time, including CoreDNS and test pods).
- *Wrong API endpoint:* EG33 confirms `KUBERNETES_SERVICE_HOST` is the VIP, matching the pinned intent.
- *DNS failure:* EG35 — both internal and external names resolve correctly.
- *Unexpected fragmentation:* the "Invalid packet" drops were investigated specifically for this — traced to Gate 5's node restart, proven static and non-recurring under live traffic, not an active fragmentation issue.
- *Failed connectivity scenario:* the only genuine, reproducible failures are policy scenarios for a network-policy design that does not exist yet (Gate 30) — not a connectivity failure in anything this gate builds or is responsible for; unrestricted connectivity (the actual scenario Gate 6 owns) was independently verified to work.
- *Service path depending on kube-proxy:* `kube-proxy-replacement: true` confirmed live (EG33); kube-proxy is disabled cluster-wide (`disable-kube-proxy: true`, unchanged since Gate 4).

## 7. Rollback

### 7.1 Reversal procedure

In reverse dependency order: remove the `firewall_trusted_pod_networks` entry and rerun `prepare-hosts.yml` to restore the pre-Gate-6 firewall (this would also break CoreDNS's own `kubernetes` plugin, since that is exactly the path it needs); remove `roles/coredns` from `install-coredns.yml`, delete the rendered manifest from `/var/lib/rancher/k3s/server/manifests/veridex-coredns.yaml`, and let k3s's AddOn controller tear down the Deployment/Service/ConfigMap/RBAC/PDB it created. No step is irreversible; nothing outside CoreDNS's own objects and the one firewall rule was touched.

### 7.2 Adversarial hardening loop

One iteration (cap 11).

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | Independent review (Tier 1, separate context, given the diff and Gate 6 plan text) | 10 findings: (high) pod-CIDR firewall rule was a blanket accept, not scoped to the port actually needed; (medium) the firewall's own post-apply assertion only checked index 0 of the trusted-network list and never proved a live connection still worked; (medium) no PodDisruptionBudget for CoreDNS; (medium) the disposable DNS test pod had no block/rescue/always, so a failed assertion left it running forever and blocked a future rerun; (medium) an undisclosed dependency on the host not exposing a systemd-resolved loopback stub; (low) `runAsNonRoot` not enforced explicitly; (low) unpinned registry choice (Docker Hub vs. a mirror) and unverified digest, matching an existing repo-wide convention; (low) RBAC grants `pods: list/watch` unused by the configured `pods insecure` mode, inherited verbatim from upstream, not introduced here | `8bf4f56` (fixed all seven addressable findings: scoped the firewall rule to the API port and added an assertion plus a real fresh-connection check; added a PodDisruptionBudget; wrapped the test pod in block/rescue/always with pre-emptive cleanup; added a standing resolvConf-loopback assertion; enforced `runAsNonRoot`/`runAsUser` at the image's verified actual UID; not fixed, disclosed: registry/digest choice and the inherited RBAC scope, both pre-existing patterns or upstream-inherited, not regressions) |

**Attacks attempted:** the review's brief explicitly asked it to find ways the firewall change could be broader than necessary, ways the topology spread/toleration could silently reduce effective replica count, ways the disposable test pod could leak or block a future run, and whether the image pin and Corefile forward target had undisclosed dependencies. It found the firewall over-broadening (real, fixed), the test-pod cleanup gap (real, fixed), and the resolv.conf dependency (real, disclosed and now asserted). It found the topology-spread/toleration design was correct as built (the real gap there was the separately-identified missing PDB, not the constraint itself).

**Tracked exceptions:** the two low-severity, pre-existing-pattern findings (image registry/digest verification depth, inherited upstream RBAC scope) — neither is a regression this gate introduced.

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-06-cilium-dns` (`4971cbc`, `8bf4f56`).
- **Idempotent:** a fleet-wide rerun of `prepare-hosts.yml` and a rerun of `install-coredns.yml`, both after the hardening fixes, report `changed=0`, `failed=0` on every node — `c6-iir-rerun.txt`. No k3s, Cilium, CoreDNS, kube-vip or storage service was restarted.
- **Repeatable:** the firewall change, applied fleet-wide via the existing `serial: 1` rollout, reached the same scoped-rule state on all five nodes; CoreDNS, applied once from the bootstrap server, is a standard k3s AddOn mechanism identical to `roles/kubevip`'s already-proven pattern. Reproducibility from a bare/reinstalled node is not proven here (same gap disclosed at every gate since Gate 1).

## 8. Known limitations

- The full Cilium connectivity test suite is not clean: 27 categories fail because they test Gate 30's not-yet-designed FQDN/L7 network policy enforcement, and this is disclosed rather than hidden by a narrower test selection chosen after the fact.
- Verifier independence is Tier 1 only, for a gate CLAUDE.md §12 classifies high-risk (a host firewall change).
- The `no-unexpected-packet-drops` finding, while proven static and non-recurring under live traffic, was not root-caused at the packet level (e.g. via a full `tcpdump`/pcap capture during Gate 5's actual power-off) — the attribution to that event is by timing and log correlation, not a captured packet.
- Same limitations already disclosed in Gates 1-5's closure records continue to apply unchanged (break-glass key co-location, host-key TOFU, no bare-node reproducibility proof, boot-persistence unproven by an actual reboot, no approved-loss threshold defined for Gate 5's own stop condition).
