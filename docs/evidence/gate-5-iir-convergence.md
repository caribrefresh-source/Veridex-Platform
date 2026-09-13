# Gate 5 (partial) — fleet installed, network declarative and idempotent

Executed 2026-09-12.

## All five nodes on Ubuntu 24.04.5

| Node | SCP id | Machine | vLAN IP |
|---|---|---|---|
| veridex-server-1 | 938801 | RS 1000 G12 | 10.2.1.10/16 |
| veridex-server-2 | 938802 | RS 1000 G12 | 10.2.1.11/16 |
| veridex-server-3 | 938803 | RS 1000 G12 | 10.2.1.12/16 |
| veridex-agent-1  | 939122 | RS 2000 G12 | 10.2.1.100/16 |
| veridex-agent-2  | 939123 | RS 2000 G12 | 10.2.1.101/16 |

All: key auth only, `PasswordAuthentication no`, eth1 MTU 1500.

## Full mesh over the private vLAN

Every node to every node, 25/25 paths:

    veridex-server-1   .10=OK .11=OK .12=OK .100=OK .101=OK
    veridex-server-2   .10=OK .11=OK .12=OK .100=OK .101=OK
    veridex-server-3   .10=OK .11=OK .12=OK .100=OK .101=OK
    veridex-agent-1    .10=OK .11=OK .12=OK .100=OK .101=OK
    veridex-agent-2    .10=OK .11=OK .12=OK .100=OK .101=OK

## IIR: the hand-applied config is now declarative

During Gate 2 the netplan for server-1 and server-2 was written by hand over
SSH. That was an emergency mutation, not a permanent solution, and the repo
contract requires permanent changes to be declarative, version-controlled and
reproducible.

It now lives in `roles/common` as a Jinja template rendered from the
inventory (`private_ip`, `vlan_mac`, `private_prefix_length`), with:

  * an assert that the inventory carries the per-node facts
  * an assert that the prefix is /16 -- at /24 the kube-vip VIP falls outside
    the node subnet and ARP for it cannot resolve
  * a read-back assert that the interface actually carries the address

### Idempotence proven

    run 1: ok=7  changed=2   (all five nodes)
    run 2: ok=6  changed=0   (all five nodes)

changed=0 on the second run against the two hand-configured nodes is the
proof the declarative config and the hand-applied config agree exactly.

## Control node pinned

`ansible/requirements-python.txt` pins `ansible-core==2.21.4`, consumed by
both CI and the local control node so they cannot drift. Previously CI pinned
`2.17.*` on Python 3.11 while local ran 2.21.4 -- two different stacks
validating the same repo. ansible-core 2.21.4 requires Python >= 3.12, so CI
moved from 3.11 to 3.12.

## Defect found and fixed during this gate

`netcup-install-os.py` authenticated once and never refreshed. Keycloak access
tokens here live ~5 minutes, so a three-server fleet install hit HTTP 401
partway through: server-3 completed, agent-1's task polling died, and agent-2
never received its POST at all. A script that abandons half a fleet operation
is not reproducible. Both `api_get` and `post_image` now re-mint the access
token on 401 and retry once, with the refresh token held centrally in
`netcup-discover.py`.

## Environment note

Ansible run from a `/mnt/c` path ignores `ansible.cfg` because the directory
is world-writable, so `roles_path` is not applied and roles are not found.
`ANSIBLE_ROLES_PATH` must be set explicitly -- which is exactly what the
Hetzner CI does. Either set it, or check out to a Linux filesystem path.

## Not yet done

* roles `firewall`, `k3s-server`, `k3s-agent`, `kubeconfig`, `argocd-bootstrap`
  are still empty stubs
* k3s not installed; no cluster exists yet
* kube-vip leader election, and VIP behaviour under a real power-off and with
  three control-plane nodes, remain unproven (see gate-4 Residual)
