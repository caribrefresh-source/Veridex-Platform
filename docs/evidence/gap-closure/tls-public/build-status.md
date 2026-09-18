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
| D73-D78 first certificate | Manifests merged, issuance blocked | `letsencrypt-staging` / `letsencrypt-prod` ClusterIssuers and the `veridexeai-tls` wildcard Certificate are committed and validate against the live CRD schemas. Still no `route53-credentials` Secret, so no Order or Challenge has been attempted. Blocked solely on the AWS IAM credential (`docs/security/route53-dns01.md` runbook step 1). |
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
