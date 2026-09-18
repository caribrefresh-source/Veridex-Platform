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

---

## Credential delivery — the mechanism that actually exists

**Added 2026-09-18.** The section above requires SOPS + age before the
credential Secret may be created. That requirement cannot be met today, and
stating the conflict is required by `.claude/CLAUDE.md` §0.

`VERIFIED` 2026-09-18, by inspection of the repository and the live cluster:

- There is no `.sops.yaml` anywhere in the repository.
- `argocd-repo-server` runs a single container and has no SOPS/KSOPS plugin
  sidecar, so Argo CD cannot decrypt an encrypted manifest.
- No `sops`, `age` or `age-keygen` binary is on the operator workstation.
- The `sealed-secrets` namespace holds no workload.

So the only two ways a Secret reaches this cluster today are the Ansible
bootstrap render (`roles/argocd-bootstrap`) and a direct `kubectl apply`.

`docs/security/secret-register.yml` already records the resolution for exactly
this situation, for `grafana-admin-credentials`: *"SOPS + age was chosen as the
secret mechanism on 2026-09-17 (gate ledger O5), but Argo CD cannot decrypt
SOPS yet (Gates 21/22). Until it can, no secret value or manifest is committed
to this repository."* That entry carries `manual_only: true` and a reviewed
date.

**Decision:** `route53-credentials` follows the `grafana-admin-credentials`
precedent — applied directly, never committed, registered as `manual_only`.
This is not a new policy; it is the register's existing fallback applied to a
second secret. When Gates 21/22 land SOPS decryption, both secrets migrate
together and `scripts/New-Route53SopsSecret.ps1` becomes the path. Nothing in
this document's original section is withdrawn; it describes the target
mechanism, not the current one.

**What this costs, stated plainly:** the credential is not in Git, so it is not
reproducible from the repository and a cluster rebuild needs this runbook and
the AWS console. That is a real IIR gap (§4) and it is the reason Gates 21/22
exist. It is accepted here rather than hidden.

## Runbook — from zero to a trusted wildcard

Prerequisite: an AWS principal that may create IAM users in the account owning
hosted zone `Z01555242T3QOO9FDT59Z`. The operator workstation does **not** have
one — its only AWS profile points at `https://fsn1.your-objectstorage.com`
(Hetzner object storage), so every step in §1 is a human action.

### 1. Create the scoped credential (operator, in AWS)

```sh
aws iam create-user --user-name veridex-cert-manager-dns01
aws iam put-user-policy \
  --user-name veridex-cert-manager-dns01 \
  --policy-name veridex-route53-dns01 \
  --policy-document file://docs/security/route53-iam-policy.json
aws iam create-access-key --user-name veridex-cert-manager-dns01
```

An inline policy, not a managed one: it cannot be attached to a second
principal by accident. Capture both halves of the access key from the last
command's output; the secret half is shown exactly once.

### 2. Apply the Secret (operator, against the cluster)

Needs the break-glass kubeconfig — the daily identity is read-only.

```sh
kubectl --kubeconfig ~/.kube/veridex-netcup-breakglass.yaml \
  -n cert-manager create secret generic route53-credentials \
  --from-literal=access-key-id=AKIA... \
  --from-literal=secret-access-key=...
```

Key names are fixed by `kubernetes/infrastructure/cert-manager/clusterissuers.yaml`
and the namespace by the controller's `--cluster-resource-namespace`. Do not
put this command in shell history that is synced anywhere.

### 3. Register it

Add to `docs/security/secret-register.yml`, replacing `<date>` with the day it
was applied. `scripts/lint-secret-register.py` rejects a future date, and
`manual_only` is only valid while `status: active`, so add this **after**
step 2, not before.

```yaml
  - name: route53-credentials
    kind: kubernetes-secret
    sensitive: true
    purpose: >-
      AWS access key for cert-manager's ACME DNS-01 solver, consumed by the
      letsencrypt-staging and letsencrypt-prod ClusterIssuers via
      accessKeyIDSecretRef / secretAccessKeySecretRef. Scoped by
      docs/security/route53-iam-policy.json to TXT changes on the ACME
      challenge names in hosted zone Z01555242T3QOO9FDT59Z and nothing else.
      No tracked file declares this Secret's manifest, deliberately.
    held_in: >-
      Secret route53-credentials in namespace cert-manager on the netcup
      cluster, applied directly (kubectl), not through GitOps, for the reason
      recorded against grafana-admin-credentials. IAM user
      veridex-cert-manager-dns01.
    provider: aws
    status: active
    manual_only: true
    manual_only_reviewed: "<date>"
```

### 4. Watch the staging certificate issue

```sh
kubectl -n site describe certificate veridexeai-tls
kubectl -n site get certificaterequest,order,challenge
```

Expect the Challenge to reach `valid` within a few minutes; Route 53
propagation is the slow part. Two failure signatures are worth naming:

- `AccessDenied ... route53:ListHostedZonesByName` — the `hostedZoneID`
  reasoning in `clusterissuers.yaml` was wrong. Add that one action to
  `route53-iam-policy.json` and re-apply the user policy. Widen nothing else.
- Challenge stuck `pending` with the TXT record visible in Route 53 — normal
  propagation; cert-manager self-checks authoritative nameservers first.

### 5. Promote to production

Only once step 4 shows `Ready=True`. In
`kubernetes/applications/site/certificate.yaml` change `issuerRef.name` from
`letsencrypt-staging` to `letsencrypt-prod`, commit, and let Argo CD sync.
cert-manager reissues into the same Secret and Traefik reloads it without a
restart.

Verify from outside the cluster, against a worker public IP, because the apex
still resolves to Squarespace until the Stage F cutover:

```sh
openssl s_client -connect 159.195.197.136:443 -servername www.veridexeai.com \
  </dev/null 2>/dev/null | openssl x509 -noout -issuer -subject -ext subjectAltName
```

The issuer must be Let's Encrypt (not `CN=TRAEFIK DEFAULT CERT`, not
`(STAGING)`), and the SAN list must contain both `veridexeai.com` and
`*.veridexeai.com`. Use a `*.veridexeai.com` name for the SNI, as above — it is
the only check that proves the wildcard half is real.

### 6. Rollback

Revert the `issuerRef` change (back to staging), or revert
`kubernetes/applications/site/ingressroute.yaml` to `tls: {}`, which returns
443 to Traefik's self-signed certificate. Both are pure Git reverts; the site
keeps serving throughout either. To withdraw the credential entirely:
`aws iam delete-access-key`, then delete the Secret and the register entry.
