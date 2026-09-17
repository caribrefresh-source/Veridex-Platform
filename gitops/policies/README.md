# Policies

The fourth thing the Initial Stages Plan's GitOps boundary says Argo CD owns, alongside cluster services, data services, and applications (plan text, line 53). Empty until the first real policy lands — this directory exists now so policy manifests don't end up sprawled implicitly inside `infrastructure/` the way they did in the K3s-HA repo. <!-- provider-drift-ok: historical source platform comparison -->

## What did *not* get ported from K3s-HA, and why <!-- provider-drift-ok: historical source platform comparison -->

K3s-HA's `gitops/policies/` has two Rego files, `resource-limits.rego` and `scaling-capacity.rego`. Both were read in full before deciding what to do with them, and both turned out to be **non-functional stubs**, not working policy: <!-- provider-drift-ok: historical source platform comparison -->

- `resource-limits.rego`'s stated intent (per its own comment) is "deny if memory limit requested > 80% of node capacity," but the rule body only checks `input.kind == "Pod"` and reads the memory limit — it never compares that limit against 80% of anything. As written, it denies *every* Pod that sets a memory limit at all, unconditionally, regardless of size.
- `scaling-capacity.rego`'s stated intent is "block scaling if requested CPU > 90%," but the rule body only checks `input.kind == "Deployment"` — it denies *every* Deployment, unconditionally.

Copying these into a repo that's meant to actually gate netcup deployments would mean shipping admission rules that block everything they touch the moment they're wired to a real admission controller. They were left out. Real OPA/Kyverno admission policy for this cluster is already gated explicitly — see the Initial Stages Plan's Gate 34 (namespace RBAC), which states the admission mechanism is "Kyverno or OPA — mechanism not yet chosen." Write real policy there, against that gate's acceptance criteria, rather than resurrecting K3s-HA's stubs. <!-- provider-drift-ok: historical source platform comparison -->

## What did get ported: the consumer-capability-gates mechanism

`consumer-capability-gates.yaml` in this directory is a scaffold, not a working copy — see that file's own header for what it is and why it's currently empty of actual gates. Unlike the Rego files, this mechanism in K3s-HA is real and proven: it's a CI-time (not admission-time) data-driven contract system that catches a specific class of defect no single service's health check can see — two independently-healthy, independently-deployed services whose *combination* is broken (K3s-HA's own history: a backend enforcement flag activated before the frontend UI that depended on it had actually deployed, silently hiding data for ~20 hours with every individual health check green). That mechanism is worth having here before this repo has enough interdependent services for the same class of defect to become possible — but there's nothing to gate yet, since `applications/` and `platform/` are both still empty. <!-- provider-drift-ok: historical source platform comparison -->

Populate this file with real gates, and wire in a checker script (K3s-HA's `scripts/check-consumer-capability-gates.py` is the reference implementation to adapt, not to copy — its manifest paths are K3s-HA-specific), once the first pair of interdependent services actually lands in `applications/` or `platform/`. <!-- provider-drift-ok: historical source platform comparison -->
