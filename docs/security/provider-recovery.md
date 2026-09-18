# Provider-level administrative recovery

Use this runbook when SSH cannot work because the node OS, SSH service,
firewall, or authorized-key file is unavailable. It is separate from the
emergency SSH credential and must not depend on either workstation-held SSH
private key.

## Preconditions

- The Production Infrastructure Owner maintains the netcup account recovery,
  MFA, and authorized-contact information outside this repository.
- An authorized operator opens an incident record using
  `emergency-access-record-template.md`.
- Before changing a server, record its identity, current power state, expected
  host fingerprint, and available backup/restore evidence.

## Recovery sequence

1. Sign in to the provider control plane using its independently recoverable
   account path. Stop if server identity is ambiguous.
2. Prefer the least invasive available channel: remote console first, then a
   provider rescue environment. Do not reinstall the OS merely to repair SSH.
3. Mount or enter the installed system and diagnose power, disk, network,
   firewall, `sshd`, and `/root/.ssh/authorized_keys` state.
4. Restore the exact public-key list from
   `ansible/inventory/production/group_vars/all.yml`; never transfer a private
   key to the node.
5. Restore normal boot, verify the host key against the trusted baseline, and
   test both routine and independently held emergency access.
6. Run `prepare-hosts.yml` serially to converge the repaired node, then execute
   the applicable cluster-health checks.
7. Record provider actions, node evidence, authentication results, and any host
   key change. A changed host key requires an explained rebuild/rekey event and
   controlled baseline update; never accept it interactively without review.

## Recovering from a Cilium host policy that blocks access

A host policy (`CiliumClusterwideNetworkPolicy` selecting the host endpoint) can
drop inbound traffic to a node, including SSH. This section is the recovery for
that specific case, and it inverts the usual instinct.

**Do not stop the Cilium agent.** Cilium pins its eBPF programs to bpffs, so the
datapath keeps enforcing after the agent process exits (`DOCUMENTED`, Cilium
host-firewall documentation and datapath source). Stopping the agent — or the
k3s service that runs it — removes the only thing that can *change* the policy
while leaving the enforcement in place. Both recovery paths below require the
agent to stay running.

The same applies to `kubectl` from the operator workstation: it reaches the API
through an SSH tunnel (see `emergency-access.md`), so it is unavailable in
exactly this scenario. Recovery runs from the node's own console.

### Server nodes

A k3s server holds a local kubeconfig and serves the API on loopback, which a
host policy does not filter. Delete the offending policy:

```sh
k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml \
  delete ciliumclusterwidenetworkpolicy <policy-name>
```

### Worker nodes

A k3s agent has **no** `/etc/rancher/k3s/k3s.yaml` (`DOCUMENTED`, k3s
distributes a kubeconfig to servers only), so the step above does not exist
there. Instead, reach the running agent through the container runtime and put
the host endpoint back into audit mode, which turns policy drops into warnings
without altering the policy:

```sh
k3s crictl ps | grep cilium-agent
k3s crictl exec -it <container-id> cilium-dbg endpoint list
k3s crictl exec -it <container-id> \
  cilium-dbg endpoint config <host-endpoint-id> PolicyAuditMode=Enabled
```

The host endpoint is the one whose labels include `reserved:host`. Audit mode is
temporary and does not survive an agent restart, so it buys access to fix the
policy properly — it is not the fix.

### Afterwards

Removing the policy or enabling audit mode on the node is an emergency mutation
under `.claude/CLAUDE.md` §4, and the live cluster now differs from Git. If the
policy is still committed, Argo CD's `selfHeal` will re-apply it within a sync
interval and the node will lock again. Revert the commit as well, then record
the incident.

## Rebuild and restore

If repair is impossible, follow the repository's node rebuild and data-restore
procedures. Confirm backups before destructive provider actions. Reinstallation
or disk replacement requires explicit Production Infrastructure Owner approval.

## Validation status

This runbook is documented but not yet live-proven. The open remediation
register tracks a provider-console/rescue drill. It is not closed until an
authorized operator demonstrates account recovery, non-destructive console or
rescue access, and restoration of normal SSH without exposing private keys.

The drill must additionally exercise the host-policy recovery above **before any
host-policy enforcement work** (Public TLS plan Stage E): a console shell on one
server and one worker, and the node-appropriate recovery command actually run on
each. The two paths differ, and the worker path is the one that fails silently
if `crictl` access has never been tested.
