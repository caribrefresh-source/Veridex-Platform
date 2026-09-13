# Gates 2-3 — private vLAN configured and path MTU measured

Executed 2026-09-12 on `veridex-server-1` (10.2.1.10) and `veridex-server-2`
(10.2.1.11), both reinstalled to Ubuntu 24.04.5 LTS.

## Configuration applied

`/etc/netplan/60-private-vlan.yaml` on each node, mode 0600, matching on MAC
rather than interface name (netcup's own delivered netplan matches on MAC too):

    eth1: match.macaddress -> addresses: 10.2.1.{10,11}/16, mtu 1500,
          dhcp4/dhcp6 false, accept-ra false

Deliberately a separate 60- file rather than editing netcup's delivered
50-cloud-init.yaml, so cloud-init regenerating that file cannot clobber it.

## The /16 mask, proven

    10.2.0.0/16 dev eth1 proto kernel scope link src 10.2.1.10

The kernel route covers the whole 10.2.0.0/16 and therefore includes the
kube-vip VIP at 10.2.0.100. Had the interface been configured /24, the route
would have been 10.2.1.0/24 only, the VIP would have been off-subnet, and ARP
for it could never have resolved without an added static route.

## L2 connectivity across the netcup Cloud vLAN

    ping 10.2.1.10 -> 10.2.1.11 : 3 transmitted, 3 received, 0% loss
    rtt min/avg/max/mdev = 0.340/0.786/1.603/0.578 ms
    ip neigh: 10.2.1.11 lladdr ca:b5:7f:4b:2a:47 REACHABLE

Sub-millisecond RTT, comfortable for etcd Raft. ARP resolution works across
the vLAN -- the first real evidence that kube-vip's ARP-based VIP is viable
on this platform, though VIP failover itself is still unproven (Gate 4).

## Path MTU = 1500 exactly

    payload 1472 (1500 on wire) : PASS
    payload 1473 (1501 on wire) : fail
    payload 8972 (9000 on wire) : fail

No jumbo frames. eth0 (public) is also 1500, so the two never disagree and
Cilium's auto-detection cannot pick a wrong value.

## cilium_mtu stays unset — evidence, not omission

Checked against the live Hetzner cluster: its Ansible role passes
`--set mtu=1360`, but `kubectl -n kube-system get cm cilium-config -o
jsonpath='{.data.mtu}'` returns EMPTY, and every Cilium device runs at 1400:

    cilium_vxlan mtu=1400   cilium_host mtu=1400
    cilium_net   mtu=1400   eth0        mtu=1400

1400 is the auto-detected host MTU. The 1360 setting has never taken effect.
Cilium auto-detects the underlay and subtracts VXLAN and WireGuard overhead
itself. netcup therefore gets the same treatment: auto-detect from 1500.

This also corrects an earlier claim in this project's notes that
`cilium_mtu` "is wired" via `--set mtu=`. The flag is present in the install
command, but it demonstrably does not reach cilium-config.

Verify after Cilium install that cilium_vxlan lands at a sane value.

## State after these gates

| Node | OS | vLAN IP | Status |
|---|---|---|---|
| veridex-server-1 | Ubuntu 24.04.5 | 10.2.1.10/16 | configured |
| veridex-server-2 | Ubuntu 24.04.5 | 10.2.1.11/16 | configured |
| veridex-server-3 | Debian 13 (stock) | - | awaiting reinstall |
| veridex-agent-1  | Debian 13 (stock) | - | awaiting reinstall |
| veridex-agent-2  | Debian 13 (stock) | - | awaiting reinstall |
