# Finding: NodePort and hostPort bypass the host firewall

**Date:** 2026-09-17
**Severity:** High — a documented security control does not do what it says.
**Status:** Preventive control shipped (admission policy). Network-layer
enforcement still outstanding — see *Remediation*, item 2.

---

## Summary

`roles/firewall` states, in its own defaults file, that *"the private vLAN is
trusted in full; the public interface allows only SSH plus whatever is
explicitly published."*

That is **false for all Kubernetes service traffic.** With Cilium running
`kubeProxyReplacement=true`, NodePort and hostPort traffic is handled in eBPF at
tc ingress — **before** netfilter's INPUT chain ever sees the packet. The
`firewall_public_tcp_ports` allowlist has no effect on it.

Every NodePort in this cluster is reachable from the public internet, on every
node, whether or not the firewall lists it.

## Evidence (`VERIFIED`, 2026-09-17)

Tested live against the production cluster and then removed. Two probes:

| Probe | Firewall allowlist | Result from the public internet |
|---|---|---|
| Pod with `hostPort: 80` on `veridex-agent-1` | 80 not listed | **HTTP 200** |
| `Service type=NodePort`, `nodePort: 31500` | 31500 never listed | **HTTP 200** on `veridex-agent-1` |
| Same Service, via `veridex-server-1` | 31500 never listed | **HTTP 200** |
| Control: `veridex-agent-2:80`, no pod bound | 80 not listed | timeout (correct) |

The control matters: the firewall *does* block a port with nothing behind it.
It simply never gets consulted once Cilium is serving that port. `nftables` is
not being bypassed by a misconfiguration — it is being bypassed by design, by
the datapath sitting in front of it.

The probe pods were deleted immediately; both ports were re-tested afterwards
and no longer answer.

## Consequences

1. **The stated security model is wrong.** Anything that reads
   `roles/firewall/defaults/main.yml` and concludes the public attack surface is
   "SSH plus 32537 and 32538" is mistaken.
2. **Any principal who can create a Service or a Pod can publish to the public
   internet.** No firewall change, no node access, no approval step. There is
   currently no NetworkPolicy enforcement (`k3s disable-network-policy: true`)
   and, before this finding, no admission control either.
3. **An earlier change claimed an effect it did not have.** PR #51/#52 added
   TCP 32538 to `firewall_public_tcp_ports` "so Grafana can be reached". Grafana
   was already reachable on 32538 before that ran. The Ansible change was a
   no-op for reachability; its commit message overstates what it achieved. The
   change is harmless and is retained — it correctly documents *intent*, and it
   would become load-bearing the moment the bypass is closed — but the record is
   corrected here.
4. **`enable-host-firewall` is `false`** in the live Cilium config, which is why
   nothing enforces at the layer that is actually handling these packets.

## Remediation

### 1. Admission control — shipped with this finding

`kubernetes/cluster/policies/host-exposure.yaml` adds two native
`ValidatingAdmissionPolicy` objects (no new controller, no Cilium restart):

- `veridex-deny-hostport` — denies `hostPort` on containers, initContainers and
  ephemeralContainers.
- `veridex-deny-nodeport` — denies Services of type `NodePort` **and**
  `LoadBalancer`. LoadBalancer is included because it still allocates a node
  port, and with no LoadBalancer controller on netcup such a Service would sit
  Pending while its port was already live — exposed and looking broken.

`kube-system` is exempt, because the ingress controller legitimately publishes
there. Everything else is denied; application workloads reach the internet
through Traefik.

This is **preventive, not a network control.** It stops new exposure being
created. It does not filter traffic to anything already exposed, and it does not
constrain a principal who can bypass admission. It is defence in depth, not a
replacement for item 2.

### 2. Cilium host firewall — NOT done, needs authorization

The architecturally correct fix is to enforce at the layer doing the work:
set `enable-host-firewall=true` and express the host's ingress rules as a
`CiliumClusterwideNetworkPolicy`. That is what would make the "only what is
explicitly published" claim true again.

It is not done here because it requires a Cilium configuration change and a
DaemonSet restart, and **CLAUDE.md §9 forbids routine Cilium restarts without
root-cause analysis and explicit authorization**. This finding is that analysis.
The decision is the repository owner's.

Until then the host firewall remains meaningful for everything that is *not*
Kubernetes service traffic — SSH, and any host-level listener — and meaningless
for anything Cilium is serving.

### 3. Documentation corrected

`roles/firewall/defaults/main.yml` now states the limitation at the point where
the false claim was made, so the next person to read it is not misled.

## What this does not change

- No evidence of misuse. The exposed ports found were Traefik's own (32537,
  32538), both intended to be public, plus the two probes created and destroyed
  during this investigation.
- Grafana's exposure is unchanged and was always intentional.
- The vLAN trust model is unaffected: `10.2.0.0/16` remains trusted in full, and
  that is still enforced by nftables for non-service traffic.
