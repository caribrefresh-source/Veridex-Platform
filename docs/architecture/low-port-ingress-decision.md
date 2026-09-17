# Low-port ingress — mechanism and node placement

**Status:** Decided 2026-09-17. Implements deliverable D96 of
`docs/Engineering Documents/Gap Closure Plan — Public TLS.md` (Stage C, as
amended by Rev 3a).

Every claim carries a `.claude/CLAUDE.md` §1 evidence label.

## 1. Mechanism: hostPort

Traefik publishes host ports 80 and 443 directly from a DaemonSet.

| Alternative | Verdict | Why |
|---|---|---|
| **hostPort** (chosen) | Adopted | Cilium reports `HostPort: Enabled`, and a test pod bound host :80 and served traffic — `VERIFIED` by the Stage C spike. |
| nftables DNAT from 80/443 to the NodePort | Rejected | Moot once hostPort was proven. It would also add a host-level rule set that Ansible owns and Argo CD cannot see. |
| Widening the k3s NodePort range to include 80/443 | Rejected | Any Service in any namespace could then claim port 80 or 443 cluster-wide. |
| MetalLB / a public service VIP | Rejected for now | The netcup Cloud vLAN is private and nothing here can advertise a public address. Whether netcup offers a movable failover IP is `UNKNOWN` — confirm with the provider before revisiting. Even then, moving it needs a provider API call, which is outside MetalLB's model. |
| A separate HAProxy or nginx tier | Rejected | Internet → proxy → Traefik → service duplicates Traefik's job and adds a second TLS and configuration system for no benefit at this size. |

`NET_BIND_SERVICE` is **not** required: the container listens on 8000/8445 and
the datapath maps the host ports, so the pod keeps `drop: [ALL]` and
`readOnlyRootFilesystem: true` — `VERIFIED` by the same spike.

## 2. Placement: the two worker nodes

`nodeSelector: veridex.io/role: worker` — `veridex-agent-1` and
`veridex-agent-2`. Public TLS termination stays off the control-plane/etcd
nodes: their blast radius is the whole cluster, and etcd is the most
latency-sensitive component in it. Capacity is not the reason — the workers
measured **2.5% CPU and ~11% memory of 8 vCPU / 16 GiB** on 2026-09-17
(`VERIFIED`, VictoriaMetrics), against a Traefik request of 100m / 128Mi.

## 3. What this placement costs

- **Two public ingress IPs, not five.** Availability rests on Route 53
  multivalue-answer records with one health check per record. Simple records
  cannot carry health checks (`DOCUMENTED`, AWS Route 53 docs).
- **DNS failover is not load balancing.** Detection takes roughly three checks
  at the configured interval, plus the record TTL. Clients holding a cached
  answer or an open connection still fail. A large document upload or a
  WebSocket session on a failed node **breaks**; it does not migrate. Clients
  must retry. Keep the TTL at 60s.
- **Route 53 health checkers must be allowed** to reach 80/443 once the Stage
  D/E host policy enforces anything, or the checks fail closed and take the
  records out of service. AWS publishes the checker ranges; they change, so the
  allowance needs a review cadence rather than a one-time copy.

## 4. Long-term target: two dedicated ingress nodes

Agreed direction, not yet scheduled. The trigger is measured contention, not a
date: the same two workers are slated to be Longhorn storage nodes and MinIO
failure domains (Gates 12, 13, 26), so public upload traffic would share a NIC
and disk queue with replication, and draining a worker for ingress maintenance
would also remove a storage domain.

Moving there changes a `nodeSelector` and the DNS records — not the mechanism —
which is why building on the workers now is not throwaway work.

When those nodes are provisioned (`veridex-ingress-1`, `veridex-ingress-2`),
each of the following must be handled, and each is easy to miss:

- **Public IPv4 per node, on the existing private vLAN**, addressed from the
  register in `ansible/inventory/production/group_vars/all.yml` — never
  hardcoded (CLAUDE.md §2).
- **Taint the nodes for ingress only.** Then add tolerations to every DaemonSet
  that must still run there — at minimum Cilium, node-exporter and Fluent Bit.
  Without them the nodes go dark in monitoring and lose their CNI.
- **Exclude them from Longhorn** (storage-eligible false, or a node tag the
  StorageClasses do not select), so no replica is ever placed on an ingress
  node.
- **No CNPG, MinIO, Temporal, NATS or inference workloads**, enforced by the
  taint plus explicit affinity on those workloads.
- **Host policy first.** See §5: a firewall entry alone does not gate this
  traffic.
- **Move the Route 53 records and health checks** to the new addresses, then
  remove the worker IPs — in that order, with both sets live in between.

## 5. The firewall does not gate this traffic

`ansible/roles/firewall` cannot restrict hostPort or NodePort traffic. With
Cilium `kubeProxyReplacement=true`, that traffic is handled in eBPF at tc
ingress, before netfilter's INPUT chain — proven live and recorded in
`docs/security/nodeport-bypasses-host-firewall.md`. Opening 80/443 there is not
required for this to work, and presenting it as the control would be theatre.

The real control is the Cilium host policy in Stages D–E.
`enable-host-firewall` is already `true` cluster-wide, but **zero**
`CiliumClusterwideNetworkPolicy` objects exist, so it currently enforces
nothing — `VERIFIED` 2026-09-17. Until those policies land, a node designated
"ingress only" is a node that carries public traffic, not one that refuses
everything else.
