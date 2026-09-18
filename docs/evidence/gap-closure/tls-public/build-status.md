# Public TLS gap-closure build status

**Updated:** 2026-09-18

This record reports only directly observed state. It does not close a numbered
platform gate; the public-TLS work is the separate gap-closure plan documented
in `docs/Engineering Documents/Gap Closure Plan — Public TLS.md`.

## Current status

| Scope | Status | Evidence |
|---|---|---|
| D63-D64 Route 53 DNS | Built, propagation ongoing | The apex registrar delegation returned the four Route 53 nameservers from 1.1.1.1 and 8.8.8.8 on 2026-09-17; the workstation resolver still cached Squarespace. Existing website records continue to target Squarespace. The child `k8s` zone remains delegated. |
| D68-D72 cert-manager platform | Built and live | `cert-manager` Argo CD Application was `Synced/Healthy`; all three controller pods were Ready on 2026-09-17. |
| D73-D78 first certificate | Blocked | No Route 53 credential Secret, ClusterIssuer, Certificate, Order, or Challenge exists. |
| D88-D89 site source and rebrand | Built | `apps/site/` contains only `/`, `/plans`, and not-found behavior. ESLint, TypeScript, 5/5 tests, production build, production dependency audit, Docker build, and container checks passed. |
| D90 immutable image | Published and anonymously pullable | `ghcr.io/caribrefresh-source/veridex-site@sha256:63c80dd7b81837a7600c2c82ee0ea6f9123f5727a2d843a04a91e86fea15022a`; GitHub reported public visibility and a credential-free pull of this exact digest succeeded on 2026-09-17. The image also passed a read-only-root-filesystem health check. |
| D91 site namespace | Built and reconciled | `cluster-namespaces` was `Synced/Healthy` at merge commit `3ac19358068d594326cc540206262cad62c9d340`; namespace `site` exists. |
| D92 workload and Argo CD Application | Built and reconciled | Digest-pinned Deployment, ClusterIP Service, and `site` Application were `Synced/Healthy` at the merge commit. |
| EG90-EG94 | **PASS** | See `stage-b/eg90-eg94.txt`; live checks completed 2026-09-17. |
| Stage C low-port ingress | **Built and live** | `traefik-ingress-ds` (worker-only DaemonSet, `veridex.io/role=worker`) 2/2 Ready; live `hostPort` map `web c:8000 h:80`, `publicsecure c:8445 h:443`. Probed from outside on 2026-09-18: both worker IPs return `301 -> https://veridexeai.com/` on :80 and `200` on :443 with SNI `veridexeai.com`; control-plane `152.53.177.26:80` does not answer. This supersedes the 2026-09-17 "not started" reading, which was written before the Stage C merge. |
| D73-D78 first certificate (staging) | **PASS** 2026-09-18 (superseded by production, below) | Both ClusterIssuers reached `Ready=True` (ACME accounts registered against the staging and production endpoints). Order `valid`; both Challenges `valid` / "Successfully authorized domain" -- the wildcard identifier authorized first. `Certificate veridexeai-tls` `Ready=True`, notAfter 2026-12-17T17:47:03Z. Both worker IPs served `issuer=C=US, O=Let's Encrypt, CN=(STAGING) Ersatz Emmer YR2`, `subject=CN=veridexeai.com`, `SAN=DNS:*.veridexeai.com, DNS:veridexeai.com`, requested with SNI `www.veridexeai.com` so the wildcard half is what matched. Traefik loaded the Secret with no restart. |
| IAM scope | **VERIFIED, including adversarially** | The `hostedZoneID` setting removes any need for `route53:ListHostedZonesByName`: the TXT record was written to `_acme-challenge.veridexeai.com` while the same credential is refused both `ListHostedZones` and `ListHostedZonesByName`. The committed policy is sufficient as written; do not widen it. Observed detail worth recording: cert-manager solved the two identifiers **sequentially**, replacing the single TXT value between them, rather than publishing two values at once. Only the record *name* matters to the policy, so this changes nothing. |
| D73-D78 production promotion | **PASS** 2026-09-18 | `issuerRef` reconciled to `letsencrypt-prod` at merge `99f3dd7`. cert-manager reported `Ready=False/IncorrectIssuer` (the expected trigger), ran a second Order against the production endpoint, both Challenges `valid`, `Certificate Ready=True`. notBefore 2026-09-18T17:57:05Z, notAfter 2026-12-17T17:57:04Z, renewalTime 2026-11-17T17:57:04Z. No window without a certificate: 443 kept serving the staging chain until the new one replaced it in the same Secret, and Traefik reloaded without a restart. |
| EG-TLS behaviour verified | **PASS** 2026-09-18 | From outside the cluster, against **both** worker public IPs, chain validated against the system trust store (no `-k`): `issuer=C=US, O=Let's Encrypt, CN=YR2`, `subject=CN=veridexeai.com`, `SAN=DNS:*.veridexeai.com, DNS:veridexeai.com`. `https://veridexeai.com` 200 and `https://www.veridexeai.com` 200 -- the apex via its own SAN, `www` via the wildcard. `https://anything.veridexeai.com` completes the TLS handshake and returns 404, which is the correct shape: the wildcard covers TLS for any subdomain while routing stays explicit per IngressRoute. Port 80 returns `301 -> https://veridexeai.com/`. Control-plane IP still silent on 443. |
| Renewal | Automatic, and alerted | cert-manager renews at `renewalTime` (2026-11-17, ~30 days before expiry) with no manual step; the Secret name does not change, so Traefik needs no edit. Expiry is covered by the existing `certificates` alert group in `kubernetes/infrastructure/monitoring/vmalert-deployment.yaml`, which evaluates `certmanager_certificate_expiration_timestamp_seconds - time()`. The renewal has NOT been drilled -- first real renewal is the test. |
| Stages D-F | Not started | No host-policy enforcement, production certificate promotion, or apex cutover. |

## Blocking operator checkpoints

1. ~~Create the Route 53 IAM credential~~ — **done 2026-09-18.** IAM user
   `veridex-cert-manager-dns01` in account 372083591392, carrying
   `docs/security/route53-iam-policy.json` as an inline policy, no console
   access. Secret `route53-credentials` applied to namespace `cert-manager`.
   `VERIFIED` adversarially with the issued key: it can read record sets in
   zone Z01555242T3QOO9FDT59Z, and is refused `route53:ListHostedZones` and
   `route53:ListHostedZonesByName` — confirming the scope is real and not
   merely declared.
2. ~~Approve and configure the SOPS+age decryption mechanism for Argo CD~~ —
   superseded 2026-09-18. SOPS exists nowhere in this repository or cluster,
   so `route53-credentials` follows the `grafana-admin-credentials`
   precedent instead: applied by `kubectl`, never committed, registered
   `manual_only`. Reasoning and the accepted IIR cost are in
   `docs/security/route53-dns01.md`. `scripts/New-Route53SopsSecret.ps1` is
   retained for when Gates 21/22 land SOPS decryption.
3. Stage C is done. Stages D–E (host policy) remain prerequisites for the
   Stage F **apex cutover**, but not for certificate issuance — DNS-01 does
   not touch the ingress path.

Stage B's "internal-only" note no longer holds: the public IngressRoute and
host ports 80/443 are live and serving (Stage C). What is still absent is a
trusted certificate and the apex A-record cutover.

The certificate served on 443 today is `CN=TRAEFIK DEFAULT CERT`, Traefik's
built-in self-signed fallback, `VERIFIED` on both worker IPs 2026-09-18. The
`site` IngressRoute now names `secretName: veridexeai-tls`; until cert-manager
populates that Secret, Traefik keeps falling back to the self-signed
certificate rather than failing the route. A 200 on 443 therefore still does
not mean TLS is trusted.

The PowerShell bootstrap script parses successfully, but its SOPS execution is
not an exit-gate result: `sops`, `age`, the age recipient, and AWS credentials
were absent from the operator environment during this run. It must be exercised
without printing credential values before D65-D67 can close.
