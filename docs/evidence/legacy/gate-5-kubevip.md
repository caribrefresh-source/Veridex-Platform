# Gate 5 — kube-vip: stable API endpoint

Executed 2026-09-12. kube-vip v1.2.3, ARP mode, DaemonSet on all three
control-plane nodes, VIP 10.2.0.100:6443.

## Result

    veridex-server-1   -
    veridex-server-2   HOLDS VIP        (elected leader, VIP on eth1)
    veridex-server-3   -

    from veridex-server-3:
      kubectl --server=https://10.2.0.100:6443 get nodes
        veridex-server-1 NotReady
        veridex-server-2 NotReady
        veridex-server-3 NotReady

A non-holder reaching the full cluster through the VIP is the proof. The
`NotReady` status is expected: Cilium is not installed yet.

An unauthenticated `curl https://10.2.0.100:6443/healthz` returns 401 with a
Kubernetes Status object -- which confirms the API is answering through the
VIP, rather than the connection failing.

## Why v1.2.3 and not the Hetzner pin

The Hetzner role pins v0.8.9. Between v0.8.x and v1.x the env var `vip_cidr`
was renamed `vip_subnet`; carrying the old manifest forward onto v1.x leaves
the prefix silently unset. The manifest here uses the v1.x name.

Two further differences from the Hetzner manifest, both deliberate:
  * it is a DaemonSet, not a single bare Pod. A leader-elected VIP needs one
    instance per control-plane node; a single Pod has nothing to elect between
  * KUBECONFIG points at k3s's own kubeconfig path, not the kubeadm path
    /etc/kubernetes/admin.conf, which does not exist on k3s

## The bootstrap deadlock, and what actually broke it

kube-vip reaches the API as the bare name `kubernetes`. Three attempts:

1. In-cluster config. Resolves the API via the Service ClusterIP 10.45.0.1.
   ClusterIP routing needs kube-proxy or a CNI -- kube-proxy is disabled and
   Cilium is not installed, because Cilium's k8sServiceHost is this very VIP.
   Deadlock. This is precisely why the Hetzner manifest sets KUBECONFIG; the
   path is a kubeadm artifact but the mechanism is the point.

2. Mounting k3s.yaml at /etc/kubernetes/admin.conf with KUBECONFIG set. The
   error changed -- so it took effect -- but kube-vip still resolved the name
   `kubernetes`, which escaped to netcup's public resolver (46.38.252.230)
   and returned NXDOMAIN.

3. Editing the NODE's /etc/hosts. Did nothing: the container runtime gives
   each pod its own hosts file, so a node-level entry never reaches the
   container even for a hostNetwork pod.

4. `hostAliases` in the pod spec. This is the mechanism Kubernetes provides
   for exactly this, and it works -- the name is written into the pod's own
   /etc/hosts, pointing at the API server already listening on loopback.

## Idempotence, and a guard that was wrong

The first version asserted the VIP was absent from `ip addr` anywhere. Correct
before kube-vip exists; wrong afterwards, because the elected leader is
supposed to hold it. Every re-run failed against whichever node held the VIP.

Replaced with a check for a STATIC assignment in /etc/netplan. That catches
the condition that actually matters -- something assigning the VIP behind
kube-vip's back, producing an ARP conflict and intermittent API failures --
without failing on the normal case.

Two consecutive full runs afterwards: changed=0, failed=0 on all three.

## Still unproven

Gate 4 proved the netcup vLAN tolerates an ARP VIP moving between nodes, but
using manual `ip addr add`. kube-vip's own leader election under a real node
failure, and VIP behaviour under an abrupt power-off, are still untested. Now
that the control plane is up, those are testable and should be.
