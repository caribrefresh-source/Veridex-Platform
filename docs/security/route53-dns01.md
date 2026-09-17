# Route53 DNS-01 operator checkpoint

The authoritative public zone is `veridexeai.com` (Route53 hosted zone
`Z01555242T3QOO9FDT59Z`). The least-privilege IAM contract is committed at
`docs/security/route53-iam-policy.json`; it permits TXT mutation only for the
apex and `www` ACME challenge record names.

The credential Secret contract is `route53-credentials` in the `cert-manager`
namespace, with keys `access-key-id` and `secret-access-key`. Do not create or
commit a plaintext Secret. Run `scripts/New-Route53SopsSecret.ps1` only after
the repository has an approved age recipient and Argo CD has an approved SOPS
decryption integration. Its default output is under the ignored `.tmp/`
checkpoint, not Argo CD's recursively rendered `gitops/` tree. The script
prompts for both values without echoing, keeps plaintext in process memory, and
writes only validated encrypted output. Move the encrypted manifest into an
Argo-owned path only after that path has a proven SOPS decryption integration.

Rotation uses the same script with replacement credentials, review of only the
encrypted manifest metadata, a GitOps sync, and issuer readiness verification.
If a credential is exposed, stop, deactivate it in AWS, create a replacement
through the human-controlled process, regenerate the encrypted manifest, and
review Git history and logs before deleting the compromised key.

Deployment order is SOPS integration, encrypted Secret, staging ClusterIssuer,
staging Certificate, site workload, Traefik route, and finally the production
issuer promotion. The cert-manager controller explicitly configures
`cert-manager` as its cluster-resource namespace, so the credential Secret must
remain there. No live mutation is authorized by this document.
