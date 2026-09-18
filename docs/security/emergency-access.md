# Emergency (break-glass) administrative access

This policy governs the emergency SSH identity authorized as `root` on the
five production nodes. It closes loss of the routine operator key; it does not
replace provider-level recovery for a destroyed operating system.

## Ownership and authorization

- **Policy owner:** Production Infrastructure Owner.
- **Authorized user:** the on-call production operator designated by that
  owner. Possession of a key component does not itself grant authorization.
- **Approver:** Production Infrastructure Owner or Security Owner.
- Prior approval is required when practical. An operator may act without it
  only to prevent material service or data loss, and must obtain retrospective
  review by the end of the next business day.
- The key must not be used for routine administration, automation, convenience,
  or an unapproved test.

## Credential and storage requirements

The production inventory must contain exactly one Ed25519 primary key named
`veridex-netcup-prod` and at least one cryptographically distinct Ed25519 key
named `veridex-breakglass-YYYYMMDD`. CI and `roles/ssh-access` reject missing,
malformed, undesignated, or duplicate key material.

Only public keys may enter Git. The emergency private key must be
passphrase-protected and stored independently of the routine operator
workstation, on encrypted offline media or a hardware-backed key. Its
passphrase must be held separately. The secret register records the location,
custody model, fingerprint, and review date without recording secret material.

### Current exception

The key generated on 2026-09-13 is still held at
`~/.ssh/veridex_breakglass_ed25519` on the same operator workstation as the
primary key. It protects against loss of one file, but not loss or compromise
of the workstation. Its passphrase protection has not been evidenced. This
exception remains open in
`docs/security/open-remediation-register.md`; do not describe administrative
access as fully independent until replacement and revocation evidence exists.

## Activation conditions

Use emergency access only when administrative access is required and one of
these conditions holds:

1. the primary private key is unavailable, lost, or corrupted;
2. use of the primary key is unsafe because compromise is suspected; or
3. urgent recovery requires direct node access and the routine path has failed.

If the node OS cannot accept SSH, use `provider-recovery.md` instead.

## SSH and `kubectl` are one failure domain, not two

`VERIFIED` 2026-09-17 on the operator workstation.

It is tempting to treat cluster administration as having two independent
routes — SSH to the nodes, and `kubectl` against the Kubernetes API. On this
workstation they are the same route:

- `kubectl` is configured against `https://127.0.0.1:16443`, a local address.
- That local port exists only because an `ssh.exe` process is forwarding it to
  the API server's loopback address on a node. The forwarding is set up by
  `scripts/start-netcup-kube-tunnel.ps1`.
- The tunnel terminates on **`veridex-server-1`**, a control-plane/etcd node.

Consequences, which matter most at exactly the moment they are least welcome:

1. **`kubectl` is not a fallback for a loss of SSH.** Anything that stops new
   SSH connections to that node — a host firewall rule, `sshd` failing, the
   node itself going down — also removes the API path this workstation uses.
   A recovery plan whose rollback step is "just run `kubectl delete`" has no
   independent path to run it from.
2. **An already-established session is worth more than a documented one.** A
   connection that exists before a change survives a policy that blocks new
   connections. That existing session, and the provider's out-of-band console
   (`provider-recovery.md`), are the only genuinely independent routes.
3. **`veridex-server-1` carries more than its share.** It is a control-plane
   and etcd member *and* the administrative entry point. Any staged change
   across nodes must reach it last.

**Required before any host-policy enforcement work** (Public TLS plan Stages
D–E, or any change that can filter inbound traffic on a node):

- an already-established SSH session to each node affected, opened before the
  change and left open; **and**
- confirmed provider out-of-band console access, exercised recently enough to
  be trusted — see `provider-recovery.md`, whose drill is still pending.

Audit mode does not remove this requirement. Audit mode proves which flows a
policy *would* drop; it proves nothing about whether SSH survives enforcement,
because under audit mode nothing is enforced.

Until the provider console drill is done, this workstation has **one**
administrative path to the cluster, and both SSH and `kubectl` depend on it.

## Access procedure

1. Open an incident record from `emergency-access-record-template.md` in
   `docs/security/incidents/`. Record approval or the reason prior approval
   was impossible.
2. Retrieve the emergency credential using the documented custody process.
   Do not copy it to persistent storage on the routine operator workstation.
3. Compare its public-key SHA-256 fingerprint with the value recorded in the
   secret register or approved custody record.
4. Verify the target host fingerprint against `ansible/files/known_hosts`.
   Stop on any mismatch.
5. Connect with only the intended identity enabled:

   ```sh
   ssh -o IdentitiesOnly=yes -o PasswordAuthentication=no \
     -i <retrieved-emergency-key> root@<node-public-ip>
   ```

6. Perform only the work required to restore the routine administrative path.
7. Record nodes accessed, commands or changes made, start/end time, and the
   emergency key fingerprint. Never record a private key or passphrase.

## Closeout and rotation

Before closing the incident:

1. restore or replace the primary operator credential;
2. review SSH authentication logs for the incident window;
3. remove temporary private-key copies and release custody components;
4. complete the incident record and obtain approver review by the end of the
   next business day; and
5. decide whether rotation is mandatory under the rules below.

Rotation is mandatory immediately after suspected workstation compromise,
suspected emergency-key exposure, lost custody media/token, unexpected use,
or departure of an authorized custodian. Target completion is four hours for
a suspected exposure of this internet-reachable root credential.

Use this add-test-remove sequence; never revoke the last proven access path:

1. keep an authenticated SSH session open;
2. generate a new passphrase-protected Ed25519 key in the approved independent
   custody environment;
3. add its public half to `admin_ssh_public_keys` with a dated break-glass
   comment and run `prepare-hosts.yml` (the play is serial);
4. retrieve and test the new key against all five nodes using the command
   above, validating every host fingerprint;
5. remove the superseded public key, rerun `prepare-hosts.yml`, and verify on
   every node that the new key succeeds and the old key is rejected;
6. update the secret register and attach non-secret evidence to the incident;
7. securely dispose of the superseded private-key copies.

Stop and preserve the old path if any node fails, a fingerprint changes, or
independent retrieval cannot be completed.

## Quarterly assurance drill

At least once every 92 days, an authorized operator must:

1. confirm custodians and independent storage remain correct;
2. retrieve the credential through the documented custody process;
3. validate its fingerprint and authenticate to all five nodes;
4. run only `id` and `hostname`, then confirm the attempts in SSH/system logs;
5. create an incident-format drill record and document discrepancies; and
6. update `manual_only_reviewed` in the secret register.

CI rejects a `manual_only_reviewed` date older than 92 days. The policy owner
must also review this policy annually and after every activation.

## Evidence required to close the current exception

- approved independent storage method and named custodial roles;
- new public-key fingerprint and inventory change;
- successful retrieval and authentication on all five nodes;
- confirmed rejection of the old emergency key on all five nodes;
- updated secret register; and
- completed, approved drill/rotation record.

Private keys, passphrases, recovery codes, and credential fragments are never
acceptable evidence.
