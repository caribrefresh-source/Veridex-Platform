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

## Rebuild and restore

If repair is impossible, follow the repository's node rebuild and data-restore
procedures. Confirm backups before destructive provider actions. Reinstallation
or disk replacement requires explicit Production Infrastructure Owner approval.

## Validation status

This runbook is documented but not yet live-proven. The open remediation
register tracks a provider-console/rescue drill. It is not closed until an
authorized operator demonstrates account recovery, non-destructive console or
rescue access, and restoration of normal SSH without exposing private keys.
