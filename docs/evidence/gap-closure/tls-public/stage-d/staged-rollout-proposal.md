# Stage D — staged rollout proposal

**Status:** Proposal for review. Nothing here is applied, no node is labelled,
and PR #65 is unchanged at reviewed commit `871537f`.

Supersedes, if accepted, the "apply to all five at once" shape of
`procedure.md` §2 step 4. It does not change the policy's rules — only which
nodes it selects, and in what order.

## Why this changed

`procedure.md` was written believing SSH was the escape hatch and `kubectl`
the independent fallback. It is not: `kubectl` on the operator workstation
reaches the API through an SSH tunnel terminating on `veridex-server-1`
(`VERIFIED` 2026-09-17; see `docs/security/emergency-access.md`). One node
therefore carries the control plane, an etcd member, and the only
administrative entry point this workstation has.

So the blast radius of a wrong rule is not "one node unreachable by SSH" — it
is "no SSH and no `kubectl`, at once". Applying to five nodes simultaneously
puts every recovery path behind the same single change.

## Proposed sequence

Every step is a committed Git change. **No `kubectl patch`, `kubectl label` or
edit of a live policy** — a canary that only exists as a live mutation is drift,
and it disappears on the next self-heal.

1. **Identify the tunnel endpoint.** Done: `veridex-server-1`. It goes **last**.
2. **Establish and verify the escape hatches.** An operator-held SSH session per
   node, opened before any policy is applied and left open. Operator-held by
   necessity: an agent cannot keep an interactive session alive, and an
   automated session is not an escape hatch from automation.
3. **Canary: one worker.** Add `veridex.io/host-policy: canary` to
   `veridex-agent-2` (the worker that does *not* hold the tunnel) through the
   node-label source of truth in Ansible, and commit a `nodeSelector` matching
   that label. One worker enforces nothing yet — it observes.
4. **Observe and confirm** on the canary: audit verdicts classified, SSH still
   accepted, the API still reachable, workloads healthy, and the public ports
   still answering. Stop conditions are unchanged from `procedure.md` §3.
5. **Second worker.** Extend the selector to `veridex-agent-1` in a reviewed
   commit. Re-observe.
6. **Control planes, one at a time**, with `veridex-server-1` last. Each is its
   own commit and its own observation window.
7. **Remove the canary selector** in a final reviewed change, returning the
   policy to `nodeSelector: {}` once every node has been observed individually.

## What the canary does and does not prove

- **Does prove:** the policy selects the nodes intended, Argo CD reconciles it,
  and the audit log shows which real flows would be denied.
- **Does not prove:** that SSH survives enforcement. Under audit mode nothing
  is dropped, so a rule that would sever SSH looks identical to one that would
  not. The only evidence for that is enforcement itself.

Enforcement therefore stays a separate decision (Stage E) needing, at minimum:

- explicit authorization, separate from this stage's;
- **provider out-of-band console access, confirmed working first** — the drill
  in `docs/security/provider-recovery.md` is still pending, and it is the only
  recovery path that does not run over SSH or the SSH-backed API tunnel;
- a rollback that does not depend on SSH or `kubectl`, for the same reason;
- one node at a time, starting with a worker and ending at
  `veridex-server-1`, with an established session held open throughout.

## Open question for the reviewer

`procedure.md` step 4 currently describes the all-at-once merge. If this
proposal is accepted, that step needs rewriting and PR #65's `nodeSelector`
needs a canary label before it merges — which means PR #65 as it stands
(`nodeSelector: {}`, all five nodes) would be superseded rather than merged.
That is a deliberate choice to put in front of a human, not one to make by
quietly editing a pinned, reviewed commit.
