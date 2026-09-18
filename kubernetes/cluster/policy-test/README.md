# Policy-test baseline

This permanent namespace contains disposable, label-scoped test resources only.
The committed baseline supplies quota, restricted Pod Security, a tokenless
ServiceAccount, default deny, and CoreDNS-only egress.

Runtime clients are intentionally not committed until their images are pinned
by digest and proven compatible with restricted Pod Security. Test cleanup must
delete only resources carrying `veridex.io/policy-test-run=<run-id>` and must
never delete the namespace.

