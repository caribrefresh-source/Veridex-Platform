# Workload migration inventory and dispositions

**Status:** Open working register. A source workload is not eligible for migration until every required column is evidenced.

| Workload | Live source object | Disposition | Owner | CPU actual/request/limit | RAM working-set/RSS/request/limit | Storage actual/request/growth | Dependencies and flows | Validation | Rollback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| marker-worker | Unknown | Investigate | TBD | Unknown | Unknown | Unknown | Identify callers, queue and schedule | Live/source reconciliation | Do not deploy blind |
| governance-service bundle | Argo CD Application; four Deployments | Migrate after measurement | TBD | Pending 30-day metrics | Pending 30-day metrics | Pending inventory | governance, metadata, policy and rule services counted separately | Per-service smoke and dependency tests | Revert migration wave |
| hcloud-csi | Source infrastructure | Retire; provider-specific | Platform | N/A | N/A | Replace with Longhorn where approved | Hetzner-only | No target object exists | Restore source only during rollback window |
| hetzner-ccm | Source infrastructure | Retire; provider-specific | Platform | N/A | N/A | N/A | Hetzner-only | No target object exists | Restore source only during rollback window |
| cert-manager-webhook-hetzner | Source infrastructure | Decide from authoritative DNS provider | Platform | Pending | Pending | N/A | DNS authority | DNS-01 issuance test | Retain source until issuance passes |

Allowed dispositions are `Migrate`, `Rebuild`, `Replace`, `Retire`, `Defer`, and `Investigate`. Every live Deployment, StatefulSet, DaemonSet, Job and CronJob must map to exactly one row. Argo CD Application count is not accepted as workload count because one Application may own multiple deployable workloads.
