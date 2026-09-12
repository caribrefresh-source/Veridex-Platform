# Gate 5 — Cilium CNI

Cilium 1.20.1 installed 2026-09-12. All three control-plane nodes Ready.

    Routing:              Tunnel [vxlan]   Host: BPF
    KubeProxyReplacement: True
    Encryption:           WireGuard  cilium_wg0  Port 51871  Peers: 2
    Cluster health:       3/3 reachable

Cross-node pod-to-pod verified: 0% loss, ~1.04 ms, pod CIDR 10.44.x.

## The MTU finding

Cilium was installed with MTU unset, then probed:

    node-to-node underlay (eth1)         1500  PASS
    pod-to-pod cross-node, wire 1354     PASS
    pod-to-pod cross-node, wire 1358     FAIL
    pod interface MTU as configured      1500

Pods advertise 1500 but only ~1354 bytes survive. The binding constraint is
`cilium_wg0`, which sits 95 bytes below the configured MTU.

## Setting MTU explicitly was tried and reverted

    config      pod MTU   cilium_wg0   largest working payload
    auto (0)      1500       1405            ~1354
    MTU=1350      1350       1255            ~1200

The pod-to-wg0 gap is a constant 95 bytes at any setting. Choosing a number
does not close it -- 1350 simply shifted the scale down and cost 150 bytes of
usable payload. Auto-detect has the same relative gap with more absolute
capacity, so it is the better of two imperfect options. Reverted to MTU=0.

## The finding worth keeping: the Helm key is MTU, not mtu

`--set mtu=1350` produced no mtu key in cilium-config, no device change and no
error. `--set MTU=1350` immediately produced `mtu: "1350"`. Helm accepts an
unknown --set key silently.

The Hetzner role passes `--set mtu={{ cilium_mtu }}` in lower case, which is
why its cilium_mtu: 1360 has never taken effect in production and every Cilium
device there runs at the auto-detected host MTU. Earlier in this migration
that observation was used to argue auto-detection must be correct. It is not
correct -- it is merely what happens when the setting is misspelled.

## Known gap, accepted deliberately

Pods advertise MTU 1500 while ~1354 bytes actually pass. TCP is unaffected --
MSS clamping negotiates below the limit -- which is why this is invisible in
normal operation. Large single-datagram UDP can be dropped silently. Revisit
if a workload sends large UDP. The Hetzner cluster has the same gap.

## Bugs found and fixed in the role

  * jsonpath filter with nested quotes, twice (also hit in k3s-server). All
    jsonpath with filters or literal text removed from this role.
  * drift check treated an absent mtu key as different from an explicit 0,
    so it upgraded and restarted the Cilium DaemonSet on EVERY run -- exactly
    the routine restart the repository contract prohibits. Absent and 0 now
    compare equal.

## Idempotence

Two consecutive runs after the fix: changed=0, failed=0, no restarts.

## Not ported from Hetzner

socketLB.enabled=false. The Hetzner stack needs three mechanisms to force it,
records no reason anywhere, and Cilium 1.20 changed behaviour in that area.
