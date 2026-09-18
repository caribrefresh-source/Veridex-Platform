# netcup provider firewall — an out-of-band enforcement point

**Status:** Proposal for review. Nothing is applied. No `PUT` has been issued
against any interface.

Evidence labels per `.claude/CLAUDE.md` §1.

## 1. What exists today

`VERIFIED` 2026-09-18 by reading the netcup SCP API (`GET
/servers/{id}/interfaces/{mac}/firewall`):

- Every server's **public** interface has a provider firewall, `active: true`.
- The only policy attached is netcup's own copied policy, **"netcup Mail
  block"** (drops outbound SMTP/25). No rules of ours exist.
- **Cloud vLAN interfaces are not supported**: the API returns
  `firewall.cloud.vlan.not.supported`. The provider firewall therefore covers
  the public NIC only — which is where the exposure is.
- The SCP API also exposes `rescuesystem` (currently inactive) and `snapshots`
  (none exist). It exposes **no console/VNC endpoint**, so console access stays
  a browser action.

## 2. Why this matters for the host-policy work

The Cilium host policy (Public TLS plan Stages D–E) carries a lockout risk that
has shaped every decision around it: a wrong rule drops SSH on all selected
nodes, and because `kubectl` here runs over an SSH tunnel
(`emergency-access.md`), it takes the repair path with it.

The provider firewall does not share that failure mode:

| | Cilium host policy | netcup provider firewall |
|---|---|---|
| Enforced at | the node, in eBPF | the hypervisor, above the OS |
| Bypassable by the NodePort/hostPort eBPF path | No — it *is* that path | No — it never reaches the node |
| A mistake can lock out SSH | **Yes** | Yes, but… |
| …recoverable without node access | No — needs console or rescue | **Yes — fix it through the API** |
| Can express pod/identity/CIDR-aware rules | **Yes** | No — L3/L4 on one NIC |
| Sees vLAN traffic | Yes | **No** (unsupported) |
| Lives in Git | Yes | **No** — see §4 |

The important row is the recovery one. A mistake in the provider firewall is
undone by another API call; a mistake in the host policy needs an out-of-band
path that is not yet proven.

## 3. Proposed division of responsibility

Not "instead of" — the two answer different questions.

**Provider firewall: which public ports exist at all.** Blunt, L3/L4, and the
safest place to be wrong.

| Direction | Rule | Applies to |
|---|---|---|
| Inbound | ACCEPT tcp/22 | all five nodes |
| Inbound | ACCEPT tcp/80, tcp/443 | the two worker nodes only |
| Inbound | ACCEPT tcp/32537, tcp/32538 | all five, until the NodePorts are retired (open remediation register) |
| Inbound | ACCEPT ICMP echo | all five, so nodes stay diagnosable |
| Inbound | DROP everything else | all five |
| Outbound | unchanged — keep netcup's Mail block | all five |

That ruleset alone closes the finding in
`nodeport-bypasses-host-firewall.md`: an unlisted NodePort stops being
reachable from the internet, without touching the node.

**Cilium host policy: everything the provider firewall cannot express** — vLAN
traffic, pod and identity-aware rules, and per-workload intent. It stays the
Stage D/E work, but with the blast radius of its public-port rules already
reduced, because the provider firewall is the outer gate.

## 4. What this costs, stated honestly

- **It is not in Git.** This is a real violation of the IIR principle
  (CLAUDE.md §4): the rules live in netcup's control plane, and nothing detects
  drift. Mitigation, if adopted: commit the intended ruleset as data in this
  repo and add a **read-only** verify script that compares live state against
  it, in the style of the existing `scripts/netcup-*.py` — which are
  deliberately read-only. A write path is a separate decision; the SCP API is
  unsupported by netcup and its schema has already moved once
  (`2026.0909` → `2026.0916`) during this project.
- **Two places to look.** A port could be blocked at the provider while the
  host policy allows it. Any future "why is this unreachable" investigation has
  to check both. The table in §3 exists so the split is at least predictable:
  public L3/L4 at the provider, everything else in Cilium.
- **No vLAN coverage**, so it cannot replace host policy for node-to-node
  rules.
- **Same-account risk.** Whoever holds the SCP session can change it. It is
  independent of SSH, not independent of the account.

## 5. Recommended sequence

1. Apply the §3 ruleset at the provider **first**, while the node-level policy
   is still absent. If it is wrong, the symptom is a blocked port, and the fix
   is an API call — no lockout.
2. Verify externally: the four intended ports answer, an unlisted NodePort does
   not. That closes the NodePort bypass finding on its own.
3. Then run Stage D/E for the Cilium host policy, whose public-port rules now
   sit behind a gate that already works.
4. Keep the console/rescue drill as the prerequisite for Stage E regardless.
   The provider firewall reduces the chance of needing it; it does not remove
   the need to have it.

## 6. Open decisions

- Adopt this split, or keep all inbound filtering in Cilium?
- If adopted: commit the ruleset plus a read-only verifier now, and leave
  application manual through the panel? Or build a write path against an API
  netcup does not support?
- Snapshot policy: the API can snapshot a server before risky work. Useful for
  a **worker** canary; on a control-plane node a revert rolls back an etcd
  member, so it is not a general-purpose undo.
