# 2026-09-18 — provider console drill (host-policy recovery paths)

Record per `../emergency-access-record-template.md`. No secrets: no password,
key or token appears here, only outcomes.

## Authorization

- Incident ID: 2026-09-18-provider-console-drill
- Type: drill (non-destructive)
- Requester and authorized operator: repository owner (console, via the netcup
  SCP web UI); Claude Code (SSH read-only checks and the SCP API snapshot)
- Approver: repository owner — "complete step 1 to 5 above", 2026-09-18
- Approval time, or reason prior approval was impossible: approved before start
- Retrospective review due/completed: this record

## Why this drill

The Cilium host policy (Public TLS plan Stages D–E) can drop SSH. On the
operator workstation `kubectl` runs over an SSH tunnel to `veridex-server-1`,
so SSH and `kubectl` fail together (`../emergency-access.md`). The only
independent recovery path is the provider console. It had never been
exercised, so the recovery procedure in `../provider-recovery.md` was
unproven. This drill proves it for one server and one worker, before any host
policy is enforced.

## Scope and evidence

- Start/end time (UTC): 2026-09-18 14:53 – 15:13
- Nodes accessed: `veridex-server-1` (SCP 938801), `veridex-agent-2` (SCP 939123)
- Host fingerprints verified against repository baseline: yes, for the SSH
  checks (`StrictHostKeyChecking=yes` against `ansible/files/known_hosts`).
  Not applicable to the console, which does not use SSH.
- Emergency public-key SHA-256 fingerprint: not applicable. The console uses
  the local root password, not the break-glass SSH key.

### Actions and results

| Step | Node | Path | Result |
|---|---|---|---|
| Pre-D1 snapshot `pre-d1-2026-09-18` (uuid `40d37782…`) | agent-2 | SCP API, `onlineSnapshot: true` | Created. **Paused the VM — see Findings** |
| Root password status (`passwd -S root`) | server-1, agent-2 | SSH, read-only | `P` (usable) on both — console login possible |
| Console login as `root` | server-1 | SCP **Screen** tab | **PASS** — shell at 15:06:20 UTC |
| `hostname` | server-1 | console | `veridex-server-1` |
| `k3s kubectl get ccnp` (server recovery command, read-only form) | server-1 | console | **PASS** — `No resources found` |
| Console login as `root` | agent-2 | SCP **Screen** tab | **PASS** — shell at 15:12:17 UTC |
| `hostname` | agent-2 | console | `veridex-agent-2` |
| `k3s crictl ps --name cilium-agent` (worker recovery path) | agent-2 | console | **PASS** — container `47e1df21855a2`, `Running`, attempt 0, pod `cilium-t5rm6` |
| Same container reached via SSH, host endpoint 107, `PolicyAuditMode: Enabled` | agent-2 | SSH, read-only | Matches the console exactly |
| `/etc/rancher/k3s/k3s.yaml` | server-1 / agent-2 | SSH | present / **absent** — confirms the worker path must be `crictl`, not `kubectl` |

The console runs show the commands in their harmless read-only forms (`get`,
`ps`), because no host policy exists to remove. The mutating forms —
`k3s kubectl delete ccnp …` on a server, `crictl exec … PolicyAuditMode=Enabled`
on a worker — use the same access, binaries and container shown here.

## Findings

1. **The console path works.** Both nodes accept a root login at the SCP
   **Screen** tab without SSH, and both node types' recovery commands run from
   it. This is the independent path Stage E needs.
2. **An "online" netcup snapshot is not online.** It paused `agent-2` for about
   2½ minutes (14:53:26 → 14:55:51 UTC). The node went `NotReady`, the site pod
   there stopped answering, and Argo CD on NodePort 32537 briefly returned 404.
   Everything recovered with no intervention and **0 pod restarts**; audit mode
   survived because the Cilium agent did not restart. Snapshots here need a
   maintenance window, and a control-plane snapshot would pause an etcd member.
3. **The VNC console does not accept paste by typing.** Commands had to be typed;
   the **Clipboard** button under the console is the paste route. Typos
   (`Kubectl`, `cillium`) produced misleading-but-harmless empty results — the
   runbook should use short, exact commands.

## Not exercised

- **Account recovery.** The SCP login used the normal credentials, not the
  independent recovery path. `../provider-recovery.md` still counts this as
  unproven.
- **Restoring SSH after a real failure.** SSH was never broken, so there was
  nothing to restore.
- **The three other nodes.** One server and one worker were drilled, as the
  runbook requires. The paths are identical by node type.

## Closeout

- Primary access restored and tested: not applicable (never lost)
- Exposure suspected: no
- Rotation required: no
- Temporary copies removed: yes — no credential was copied anywhere
- Secret register updated: **no — gap.** The root console passwords are now a
  proven break-glass credential but have no register entry. Their custody
  location needs the owner's input; see follow-up.
- Discrepancies and follow-up:
  - Register the root console passwords as a break-glass credential, with
    their custody location (owner).
  - Decide whether to delete snapshot `pre-d1-2026-09-18` after D1, or keep it
    until the D1 canary is proven (owner).
- Final approver and time (UTC): repository owner, on merge of the PR carrying
  this record
