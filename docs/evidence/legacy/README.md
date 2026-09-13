# Legacy evidence — recorded before Revision 3 gate numbering

**Historical.** These records were written on 2026-09-12 during the netcup
bring-up, under an earlier gate numbering. The numbers in their file names do
**not** match the gates of the Revision 3 plan
(`docs/Engineering Documents/Initial Stages Plan.txt`). They were moved here
unedited on 2026-09-13 so they cannot be mistaken for Revision 3 closure records.

## How to use them

- They are `DOCUMENTED` evidence at best: dated records, not rechecked live.
  None of them can make a Revision 3 check PASS (see
  `.claude/skills/veridex-gate/SKILL.md` §5).
- None carries a tested repository commit or a cluster API identity, both of
  which the plan requires in every evidence record.
- They are useful for knowing what was tried, what was found, and where to look
  when the Revision 3 gate is closed.
- They quote values from the Hetzner K3s-HA reference cluster for comparison.
  `.provider-drift-historical` in this directory labels that as historical for
  `scripts/lint-provider-drift.py`.
- `gate-0-preflight.txt` is raw captured output. Its last line names an older
  output path (`docs/build/evidence/…`); it is left unedited on purpose.

## Mapping to Revision 3 gates

"Not shown" means the record does not contain evidence for that acceptance
item — not that it failed.

| File | What it records | Revision 3 gate(s) | Revision 3 acceptance not shown |
|---|---|---|---|
| `gate-0-preflight.md`, `gate-0-preflight.txt`, `gate-0-fleet-state.json` | Read-only netcup SCP API discovery of the five servers before OS install: machine types, firmware, delivered OS, public and vLAN MACs, vLAN attachment, VIP unassigned. | Gate 1 (pre-install state), Gate 2 (vLAN attachment). **Not** Revision 3 Gate 0, which is the repository and provider-boundary scan. | Everything in Gates 1–2 acceptance; this is pre-state only. |
| `gate-1-server-1-install.md` | Ubuntu install on `veridex-server-1` only; OS release, kernel, disk, NICs, `PasswordAuthentication no`. | Gate 1 | Four of five nodes; chrony status; host-key fingerprint comparison; explicit root policy; access test from approved runner. |
| `gate-2-3-vlan-and-mtu.md` | Static /16 vLAN addressing, ping and path MTU (1472 passes, 1473 fails) on `veridex-server-1` and `-2`. | Gate 2 | Three of five nodes; full ping matrix; route capture for public vs private paths; second Ansible run `changed=0` (see next row). |
| `gate-5-iir-convergence.md` | All five nodes on Ubuntu 24.04.5 with key-only SSH; 25/25 vLAN mesh; netplan made declarative with a second run `changed=0`; control node pinned. | Gate 1, Gate 2 | Gate 1: chrony, fingerprints, root policy, emergency access. Gate 2: 1472/1473 test on all five nodes; route and interface capture. |
| `gate-5-firewall.md` | nftables ruleset on all five nodes; vLAN trusted; external check shows 22 open and 6443, 10250, 2379 blocked; rerun `changed=0` on the first node. | Gate 3 (firewall portion) | Longhorn preflight; Cilium preflight; systemd checks incl. open-iscsi / iscsid; full external port scan; `changed=0` rerun on all five. |
| `gate-5-control-plane.md` | Three k3s servers with embedded etcd, all etcd voters; node args incl. `--secrets-encryption`, `--tls-san` for the VIP, hourly snapshots. | Gate 4 | Encrypted-at-rest proof (no plaintext Secret in raw etcd); audit event proof; certificate SAN inspection; public DNS SAN. |
| `gate-5-kubevip.md` | kube-vip v1.2.3 DaemonSet; one leader holds the VIP; a non-holder reaches the API through it; reruns `changed=0`. | Gate 4 (API VIP present); precursor to Gate 5 | Gate 5 entirely: sustained API probe, hard power-off of the holder, interruption measurement, recovery and etcd health. |
| `gate-4-kubevip-arp-proof.md` | Manual ARP VIP move between two nodes, simulating loss with `ip link set eth1 down`. | Precursor to Gate 5 | Gate 5 entirely. The record itself states it did not test kube-vip's leader election or a hard power-off. |
| `gate-5-cilium.md` | Cilium 1.20.1, VXLAN + WireGuard, kube-proxy replacement; cross-node pod ping; MTU study; reruns `changed=0`. | Gate 6 | CoreDNS replicas, topology spread and lookups; full Cilium connectivity test after DNS; agent nodes (only the three servers were present). |
