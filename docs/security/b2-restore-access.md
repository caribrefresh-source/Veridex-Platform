# Backblaze B2 restore-operator access

Closes part of Gate 8's end state — "separate write and restore identities
exist." The write identity (`ETCD_S3_ACCESS_KEY`/`ETCD_S3_SECRET_KEY`,
`docs/security/secret-register.yml`) is a production credential Gate 9 wires
into k3s automation. This restore identity is not: it exists only for a human
operator to read back what the write identity produced.

## What exists

A Backblaze B2 application key, created 2026-09-15, held only on the operator
workstation:

- `~/.config/veridex/b2-etcd-backup-restore-key` — **never committed**,
  registered in `docs/security/secret-register.yml`.
- Restricted to the `veridex-etcd-backup` bucket, capabilities
  `listBuckets,listFiles,readFiles` only — no `writeFiles`, no `deleteFiles`,
  no `writeFileRetentions`. Verified live at Gate 8
  (`docs/evidence/gates/gate-08/c2-deny-deletion-and-retention.txt`,
  `c3-list-with-restore-identity.txt`, `c4-download-and-verify.txt`).
- Expires 2026-12-14 (90 days). No rotation alerting exists yet for this key
  — tracked under Gate 20.

## When to use it

Only during an approved recovery drill or an actual restore (Gate 9's
isolated-restore proof, or the full drill in Gate 29) — matching the plan's
Identity table: "Restore identities disabled or unused except during drills."
This key is never read by any automation or Ansible role today; nothing
breaks if it is not present.

```
export B2_APPLICATION_KEY_ID=$(head -1 ~/.config/veridex/b2-etcd-backup-restore-key | cut -d= -f2)
export B2_APPLICATION_KEY=$(tail -1 ~/.config/veridex/b2-etcd-backup-restore-key | cut -d= -f2)
b2 ls -l b2://veridex-etcd-backup/
b2 file download b2://veridex-etcd-backup/<name> <local path>
```

## Known limitations

- This key can read retention and legal-hold status on the bucket (via
  `readFiles`) but not the actual retention/legal-hold *values* on a file
  (that needs `readFileRetentions`/`readFileLegalHolds`, deliberately not
  granted) — `b2 file info`/`file download` report those fields as
  `unauthorized to read` for this identity. That is intended least privilege,
  not a defect; the authoritative retention check at Gate 8 used the master
  key for exactly that reason (`c1-create-protected-object.txt`).
- No alerting exists yet if this key is used outside an approved drill, or if
  it silently expires — both are Gate 20's territory, not built here.
- Lives on the same operator workstation as every other credential in
  `docs/security/secret-register.yml`. A compromised or lost workstation
  takes this out along with all the others — the same gap already disclosed
  in `docs/security/emergency-access.md`, not re-solved here.
