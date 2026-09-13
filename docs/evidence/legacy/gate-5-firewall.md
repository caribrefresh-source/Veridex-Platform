# Gate 5 — host firewall (nftables)

Executed 2026-09-12 across all five netcup nodes via `roles/firewall`.

## Why before k3s

k3s binds its API server to `0.0.0.0:6443` and kubelet to `10250`, and
embedded etcd listens on 2379-2380. These nodes have public IPs. Installing
k3s first would expose all three to the internet for the duration.

## Model

nftables (Ubuntu 24.04 default; ufw would fight the iptables chains k3s and
Cilium manage themselves). Single declarative ruleset, `policy drop` on input:

  * `ct state established,related accept` first -- this is what keeps an
    in-flight SSH session alive while the ruleset is being replaced
  * ICMP accepted, including path-MTU discovery. Dropping it breaks PMTUD and
    produces stalls that read as application bugs
  * `ip saddr 10.2.0.0/16 accept` -- the vLAN is trusted in full, which covers
    the entire k3s and Cilium port surface (6443, 2379-2380, 10250, 8472/udp
    VXLAN, 51871/udp WireGuard, 4240 health) without enumerating ports that
    would need maintaining as Cilium's requirements change
  * SSH always accepted on the public interface
  * forward chain `policy accept` -- pod traffic is routed, not bridged, and
    Cilium installs its own rules there

Published public ports are deliberately empty until Traefik exists.

## SSH rate limit set to 30/minute, not 10

Password auth is already off (`PasswordAuthentication no`), so a rate limit
cannot stop credential stuffing -- it only caps connection floods. Set too
low it locks out legitimate automation instead: Ansible with forks=20 plus
verification loops opens new connections in bursts, and beyond the limit they
are DROPPED, which is indistinguishable from a lockout while debugging.

## Safety measures in the role

  * `validate: nft -c -f %s` on the template -- refuses to install a ruleset
    nft itself rejects, rather than discovering a syntax error after the
    previous ruleset has been flushed
  * assert that `firewall_trusted_networks` is non-empty, since an empty list
    would drop all intra-cluster traffic and produce a cluster that cannot form
  * read-back assert that the live ruleset has the drop policy, the vLAN
    accept and the SSH accept

## Verification

Applied to `veridex-server-1` alone first, then fleet-wide.

    fresh SSH (ControlMaster bypassed) : OK
    nft policy                         : drop
    server-1 -> vLAN peers             : 4/4 OK
    other 4 nodes -> server-1 vLAN     : 4/4 OK

Fleet-wide, full mesh re-verified after the rollout -- 25/25 paths OK.

External reachability from outside the vLAN:

    port 22    OPEN
    port 6443  blocked
    port 10250 blocked
    port 2379  blocked

## Idempotence

The fleet-wide run included `veridex-server-1`, already configured:

    veridex-server-1  ok=12  changed=0
    (other four)      ok=13  changed=3

## Not yet done

Traefik NodePorts (31742 / 32537 / 30051) are not published; they get added
to `firewall_public_tcp_ports` when the Traefik role lands. No k3s installed.
