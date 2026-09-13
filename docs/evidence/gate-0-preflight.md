# Gate 0 — Pre-install evidence record

Captured 2026-09-12 from the live netcup SCP API
via `scripts/netcup-discover.py`.

**Correction (2026-09-12):** this record originally claimed no operating system
was installed. That was wrong and was never verified — the API reported
`state: RUNNING` for all five from the first discovery run, which should have
prompted the question. netcup delivered every server with **Debian 13 (trixie)
minimal** pre-installed, confirmed by the provisioning emails and by
`ssh-keyscan` against all five public IPs, whose ed25519 host-key fingerprints
match those emails exactly.

Target image for all five: `imageFlavourId=100` (Ubuntu 24.04.4 BIOS amd64).
This is **resolved from netcup's live catalogue**, not pinned — the policy is
"newest 24.04 point release netcup offers for this server's firmware", applied
per server because flavour ids are machine-type dependent.

Verified 2026-09-12 across all five servers (both RS 1000 G12 and RS 2000 G12,
28 flavours each): netcup's newest 24.04 point release is **.4**. It does not
carry 24.04.5, despite that being the latest upstream release. All five resolve
to the same id, `100`.

BIOS rather than UEFI because every server reports `uefi=False`; the cloudimg
(cloud-init) variant `117` is UEFI-only and would not boot these machines as
configured.

All five carry only netcup's stock Debian 13 minimal image — no configuration,
no data, nothing recoverable. Reinstall is destructive but loses nothing, and
this record exists so the pre-state can be reconstructed if needed.

Debian 13 is not a drop-in substitute for the Ubuntu 24.04 the reference
implementation targets: `phase-01-system-prerequisites.yml` configures the
private vLAN interface and its MTU through `/etc/netplan/` + `netplan apply`,
and Debian does not ship netplan. That task — the most important networking
step in the build — would fail as written.

| SCP id | Nickname | Machine | State | Firmware | Public IP | Public MAC | vLAN MAC |
|---|---|---|---|---|---|---|---|
| `938801` | `veridex-server-1` | RS 1000 G12 | RUNNING | BIOS | 152.53.177.26 | `3a:e4:08:af:95:9c` | `3a:e4:08:af:95:9d` |
| `938802` | `veridex-server-2` | RS 1000 G12 | RUNNING | BIOS | 152.53.140.210 | `ca:b5:7f:4b:2a:46` | `ca:b5:7f:4b:2a:47` |
| `938803` | `veridex-server-3` | RS 1000 G12 | RUNNING | BIOS | 152.53.142.131 | `26:44:f8:59:8c:67` | `26:44:f8:59:8c:68` |
| `939122` | `veridex-agent-1` | RS 2000 G12 | RUNNING | BIOS | 159.195.197.136 | `c6:e3:81:a1:5a:73` | `c6:e3:81:a1:5a:74` |
| `939123` | `veridex-agent-2` | RS 2000 G12 | RUNNING | BIOS | 159.195.197.40 | `6a:01:47:82:8c:3c` | `6a:01:47:82:8c:3d` |

**Cloud vLAN** `1006740` — name `veridex-netcup-prod-k3s`, 1000Mbit (1000 Mbit/s), site id=1 Nuremberg.

All five vNICs attached (hot-plugged, no reboot). Every vLAN interface reports
`mtu=0`, meaning the guest has not brought the link up — the real MTU is not
readable from the API and must be measured on a node at Gate 3.

kube-vip VIP `10.2.0.100` verified unassigned on every interface.

Raw API state: `gate-0-fleet-state.json`.
