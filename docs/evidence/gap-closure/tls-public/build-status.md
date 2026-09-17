# Public TLS gap-closure build status

**Updated:** 2026-09-17

This record reports only directly observed state. It does not close a numbered
platform gate; the public-TLS work is the separate gap-closure plan documented
in `docs/Engineering Documents/Gap Closure Plan — Public TLS.md`.

## Current status

| Scope | Status | Evidence |
|---|---|---|
| D63-D64 Route 53 DNS | Built, propagation ongoing | The apex registrar delegation returned the four Route 53 nameservers from 1.1.1.1 and 8.8.8.8 on 2026-09-17; the workstation resolver still cached Squarespace. Existing website records continue to target Squarespace. The child `k8s` zone remains delegated. |
| D68-D72 cert-manager platform | Built and live | `cert-manager` Argo CD Application was `Synced/Healthy`; all three controller pods were Ready on 2026-09-17. |
| D73-D78 first certificate | Blocked | No Route 53 credential Secret, ClusterIssuer, Certificate, Order, or Challenge exists. |
| D88-D89 site source and rebrand | Candidate implemented; local checks pass | `apps/site/` contains only `/`, `/plans`, and not-found behavior. ESLint, TypeScript, 5/5 tests, production build, production dependency audit, Docker build, and container checks (`/`, `/plans`, `/healthz` 200; unknown path 404) passed on 2026-09-17. |
| D90 immutable image | Published and anonymously pullable | `ghcr.io/caribrefresh-source/veridex-site@sha256:63c80dd7b81837a7600c2c82ee0ea6f9123f5727a2d843a04a91e86fea15022a`; GitHub reported public visibility and a credential-free pull of this exact digest succeeded on 2026-09-17. The image also passed a read-only-root-filesystem health check. |
| D91 site namespace | Candidate implemented | `kubernetes/cluster/namespaces/site.yaml`; not merged or reconciled yet. |
| D92 workload and Argo CD Application | Candidate implemented | Digest-pinned Deployment, ClusterIP Service, and `site` Argo CD Application are present; not merged or reconciled. |
| EG90-EG94 | Not passed | Local and repository checks pass, including a zero-error provider-drift run. These gates still require merged GitOps state and live/adversarial cluster evidence. |
| Stages C-F | Not started | No low-port ingress, host-policy enforcement, certificate promotion, or apex cutover has been merged from this candidate. |

## Blocking operator checkpoints

1. Create the Route 53 IAM credential scoped by
   `docs/security/route53-iam-policy.json`.
2. Approve and configure the SOPS+age decryption mechanism for Argo CD, then run
   `scripts/New-Route53SopsSecret.ps1` locally with the approved age recipient.
3. Review the staged rollout evidence and authorize the merge immediately before
   merging to `main`.

Until those checkpoints are complete, Argo CD cannot deploy the site or issue a
certificate, and the gap-closure acceptance gates must remain open.

The PowerShell bootstrap script parses successfully, but its SOPS execution is
not an exit-gate result: `sops`, `age`, the age recipient, and AWS credentials
were absent from the operator environment during this run. It must be exercised
without printing credential values before D65-D67 can close.
