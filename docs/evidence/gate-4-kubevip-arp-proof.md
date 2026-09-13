# Gate 4 — kube-vip ARP viability on the netcup Cloud vLAN

**Verdict: PASS.** kube-vip ARP mode is viable. The largest architectural
unknown in this build is closed.

Executed 2026-09-12 between `veridex-server-1` (10.2.1.10, eth1
3a:e4:08:af:95:9d) and `veridex-server-2` (10.2.1.11, eth1
ca:b5:7f:4b:2a:47) on vLAN 1006740. VIP under test: 10.2.0.100.

Node loss was simulated with `ip link set eth1 down` rather than a power
cycle: SSH rides on eth0, so the vLAN can be severed without losing the
control channel, and the test stays self-contained. This proves the switch
and ARP behaviour, which is what was in doubt. It does NOT exercise kube-vip's
own leader election or a full node power-off -- see Residual below.

## 1. The vLAN accepts an address netcup never assigned

This was the specific risk: netcup allocates vLAN addresses itself, and a
switch that filtered unknown source IPs would make an ARP VIP impossible.

    server-1: ip addr add 10.2.0.100/32 dev eth1 ; arping -A
    server-2: ping 10.2.0.100  -> 3/3, 0% loss, rtt avg 0.432 ms
    server-2: ip neigh -> 10.2.0.100 lladdr 3a:e4:08:af:95:9d REACHABLE

Resolved to server-1's eth1 MAC. No filtering.

## 2. Failover: binding moves and traffic follows

    server-1: ip link set eth1 down        (simulated loss while holding VIP)
    server-2: ip addr add 10.2.0.100/32 ; arping -A
    server-1: recovered as client, cache flushed
    server-1: ping 10.2.0.100 -> 3/3, 0% loss, rtt avg 0.464 ms
    server-1: ip neigh -> 10.2.0.100 lladdr ca:b5:7f:4b:2a:47 REACHABLE

The MAC/IP binding moved across the switch and a client resolved the NEW
holder.

## 3. Reverse direction

    server-2: ip link set eth1 down
    server-1: reclaimed VIP + arping -A
    server-2: ping 10.2.0.100 -> 3/3, 0% loss, rtt avg 0.360 ms
    server-2: ip neigh -> 10.2.0.100 lladdr 3a:e4:08:af:95:9d REACHABLE

Failover works in both directions. No ARP flapping or duplicate ownership
observed at any point.

## 4. Cleanup

VIP released from both nodes and confirmed unclaimed, so kube-vip owns the
address from a clean state.

## Consequence

The fallback options drafted for a Gate 4 failure -- external HAProxy pair,
single non-HA HAProxy, public control-plane addresses behind firewall rules,
BGP -- are NOT needed. Proceed with kube-vip ARP on eth1, which is already
what the Hetzner role expects (`kubevip_interface: "eth1"`), and the netcup
vLAN NIC is named eth1 too.

## Residual — still unproven

* kube-vip's own leader election and lease handling (this tested the network
  primitive it relies on, not kube-vip itself).
* A true abrupt power-off of the VIP holder. The link-down simulation leaves
  the host running; a real crash also drops etcd and the API server at the
  same instant.
* Behaviour with three control-plane nodes rather than two.

Re-test all three after the control plane is bootstrapped.
