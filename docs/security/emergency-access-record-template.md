# Emergency access record template

Copy this file to `docs/security/incidents/YYYY-MM-DD-emergency-access-<id>.md`.
Commit no secrets, private host data beyond the existing inventory, or raw logs
that could contain credentials.

## Authorization

- Incident ID:
- Type: activation / quarterly drill / rotation / suspected compromise
- Requester and authorized operator:
- Approver:
- Approval time, or reason prior approval was impossible:
- Retrospective review due/completed:

## Scope and evidence

- Start/end time (UTC):
- Reason:
- Emergency public-key SHA-256 fingerprint:
- Nodes accessed:
- Host fingerprints verified against repository baseline: yes/no
- Actions performed:
- Authentication-log review result:
- Evidence paths or commit IDs:

## Closeout

- Primary access restored and tested: yes/no
- Exposure suspected: yes/no, with rationale
- Rotation required: yes/no
- Replacement tested on all five nodes: yes/no/not applicable
- Superseded key rejected on all five nodes: yes/no/not applicable
- Temporary copies removed: yes/no
- Secret register updated: yes/no/not applicable
- Discrepancies and follow-up owners/dates:
- Final approver and time (UTC):
