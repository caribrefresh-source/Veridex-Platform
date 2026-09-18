# Wave 5 / Wave 6 resolution

The intended split is deliberate:

- Wave 5 `veridex-workers` contains Temporal workers and NATS clients.
- Wave 6 `veridex-messaging` contains Temporal Server and NATS JetStream.

Client namespaces can have policy and RBAC validated before durable backing
services are installed. Client replicas remain zero until the backing services
pass their own gates. This document is a design decision, not Gate 33 closure:
Gate 33 remains pending verification against the real Gate 14 Argo CD
Applications for NATS and Temporal.

