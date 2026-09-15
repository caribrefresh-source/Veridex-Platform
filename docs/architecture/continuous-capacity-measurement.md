# Continuous capacity measurement

**Status:** Required control from Gate 11 through completion of workload migration.

## Purpose

The source cluster's approximate 15% CPU and 70% RAM averages hid over-provisioning and OOM events. Veridex therefore measures physical, allocatable, pledged and actual capacity over time; averages alone are never migration evidence.

## Metric meanings

| Dimension | Physical / allocatable | Pledged | Actual | Failure signal |
| --- | --- | --- | --- | --- |
| CPU | `kube_node_status_capacity` / `kube_node_status_allocatable` | container requests and limits | five-minute CPU rate plus p50/p95/p99/max | throttled-period ratio, latency |
| RAM | node total / allocatable | container requests and limits | working set and RSS, both retained | OOMKilled, eviction, memory pressure |
| PVC storage | volume capacity | PVC requested bytes | kubelet used bytes and growth | >75% used, mount/stat errors |
| Node storage | filesystem size | scheduled storage commitments | available bytes, IOPS, throughput and I/O time | disk pressure, latency, rebuild duration |

Working set is the primary sizing signal because it approximates memory that cannot be reclaimed cheaply. RSS is retained beside it because neither metric alone explains every runtime or kernel accounting case. CPU throttling is a ratio of throttled scheduling periods to total periods, not a percentage of CPU time.

PVC requested capacity is logical capacity. It must not be treated as physical use: Longhorn replicas, CNPG replicas, MinIO erasure coding, snapshots and rebuild headroom are recorded separately at the gate that introduces them.

## Gate procedure

At Gate 11, prove `up{job=~"kubelet|cadvisor"} == 1` for every node and that the capacity dashboard returns non-empty CPU, memory, request, limit and filesystem series. Record a clean platform baseline.

At every subsequent gate:

1. Annotate the start and end time, commit SHA and workloads introduced.
2. Capture idle, representative load and peak/load-test intervals.
3. Record p50, p95, p99 and maximum actual CPU and memory alongside requests and limits.
4. Record PVC requested, usable, actual and growth; add physical amplification for the selected storage system.
5. Exercise the gate's failure mode and measure rescheduling, rebuild/heal load and remaining headroom.
6. Investigate every OOM, eviction, sustained throttle alert or missing-metrics interval before promotion.
7. Update requests, limits and placement from evidence; never from the old cluster's averages alone.

## Promotion stop conditions

- Missing kubelet/cAdvisor coverage for any node for ten minutes.
- Any unexplained OOMKill or eviction.
- A critical workload cannot reschedule during loss of one eligible node.
- Sustained working set above 80% of failure-mode allocatable memory.
- Sustained throttling above 25% for 15 minutes with workload impact.
- PVC or operationally usable storage above 75% after replica/parity and rebuild headroom.
- Storage rebuild/heal causes an unaccepted latency or recovery-time breach.

These conditions stop the affected workload wave. They do not prevent unrelated cluster construction when its own gate remains safe and measurable.
