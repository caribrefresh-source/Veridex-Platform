# Tenant isolation model

Veridex uses shared service namespaces. A namespace is a trust, recovery and
operational boundary; it is not the tenant boundary.

Tenant isolation is enforced and tested through:

- PostgreSQL row-level security and tenant-bound database roles;
- tenant-bound MinIO object prefixes and authorization checks;
- tenant filters on Meilisearch, Qdrant and Memgraph operations;
- immutable tenant identity in NATS messages and Temporal workflow inputs; and
- application authorization on every read and write.

A release that activates tenant data must include negative tests attempting a
cross-tenant read and write at every applicable store. Namespace-per-tenant is
out of scope unless a later ADR supersedes this model and adds provisioning,
quota, policy, credential and teardown controls.

