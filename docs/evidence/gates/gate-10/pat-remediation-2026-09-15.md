# Gate 10 PAT remediation — 2026-09-15

This is follow-up evidence. It does not rewrite Gate 10's historical closure or its disclosed stop-condition override.

## Change

- Replaced the Argo CD repository Secret's password with a fine-grained PAT.
- Repository selection: `caribrefresh-source/Veridex-Platform` only.
- Permissions: Contents read-only and mandatory Metadata read-only.
- Expiry: 2026-12-14.
- No token value was written to this evidence or command output.

## Verification

- GitHub repository read succeeded.
- `X-OAuth-Scopes` was empty, proving this is not a classic scoped PAT.
- A unique Git-reference creation request using an impossible all-zero object ID was denied with HTTP 403 at authorization. A write-capable credential would reach payload validation instead; the request cannot create repository state in either case.
- Live Secret: `argocd/argocd-repo-veridex-platform`.
- Root Application after hard refresh: `Synced`, `Healthy`.
- Reconciled revision: `53b3c1f1d012e203c7238c54289e6469a32efdf1`.
- Netcup cluster identity: kube-system UID `d7d8a462-c503-49ed-a1e0-899f372f9465`.
- Temporary patch file was removed.

## Residual risk

The operator explicitly directed that the superseded classic PAT/password be retained. It was removed from Argo CD and is not used by the cluster, but it remains a broad credential in its prior operator-controlled location. No deletion or revocation was performed.
