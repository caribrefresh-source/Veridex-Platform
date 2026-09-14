# Emergency (break-glass) admin access

Closes Gate 1 G01-C5 — "administrative access is recoverable." Before this
existed, every node had exactly one authorized SSH key
(`~/.ssh/veridex_netcup_ed25519`, installed by netcup's provisioning API);
losing it would have locked out all five nodes with no fallback.

## What exists

A second ed25519 keypair, generated 2026-09-13, held only on the operator
workstation:

- Private half: `~/.ssh/veridex_breakglass_ed25519` — **never committed**,
  registered in `docs/security/secret-register.yml`.
- Public half: committed in
  `ansible/inventory/production/group_vars/all.yml` (`admin_ssh_public_keys`,
  second entry) and deployed to `/root/.ssh/authorized_keys` on all five
  nodes by `roles/ssh-access`.

`roles/ssh-access` refuses to run at all unless `admin_ssh_public_keys` has
at least two entries, so this fallback cannot be silently removed by editing
the primary key alone.

## When to use it

Only when the primary key (`~/.ssh/veridex_netcup_ed25519`) is lost,
corrupted, or its workstation is unavailable, and administrative access to
the nodes is otherwise needed.

```
ssh -i ~/.ssh/veridex_breakglass_ed25519 root@<node public IP>
```

## After using it

1. Restore or regenerate the primary operator key.
2. If the break-glass key's private half may have been exposed by the
   incident that required using it, generate a replacement, update
   `admin_ssh_public_keys` with the new public half, and rerun
   `prepare-hosts.yml` to rotate it out. Never leave a break-glass key
   committed anywhere but as a public key in the inventory.
3. Record the incident (what happened, which key was used, whether it was
   rotated) — this file does not track individual usages; that belongs in
   the gate ledger or an incident record if one exists.

## Known limitations

- This closes "a single point of failure in *keys*." It does not provide a
  recovery path if netcup itself is unreachable, or if a node's OS is
  destroyed — that is out-of-band platform recovery, not covered by Gate 1.
- **Both keys currently live on the same operator workstation.** This closes
  the scenario Gate 1 asks about — one key file lost, corrupted, or
  mistyped — but not the workstation itself being lost or compromised,
  which would take out both at once (and every other workstation-held
  credential in `docs/security/secret-register.yml`, not just these two).
  Closing that fully means storing the break-glass private half somewhere
  genuinely independent (an offline vault, a hardware token, a sealed
  physical backup) — flagged here as a real gap, not fixed by this gate.
