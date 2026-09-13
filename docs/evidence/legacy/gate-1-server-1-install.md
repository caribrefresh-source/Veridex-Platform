# Gate 1 — veridex-server-1 OS install

Executed 2026-09-12. `POST /servers/938801/image`, task
`2b2ef4ac-a7be-4fd8-92fb-deb9ab4adcf1` -> FINISHED.

Payload: `imageFlavourId=100`, `hostname=veridex-server-1`,
`sshKeyIds=[51926]`, `sshPasswordAuthentication=false`,
`rootPartitionFullDiskSize=true`.

## Verified on the live node over SSH (key auth, no password)

| Check | Result |
|---|---|
| OS | **Ubuntu 24.04.5 LTS (Noble Numbat)** |
| Kernel | 6.8.0-139-generic, x86_64 — Cilium 1.20 needs >= 5.10 |
| Hostname | `veridex-server-1` (static and runtime) |
| Root disk | vda 256G; vda3 = 255G mounted `/` — full-disk sizing applied |
| Public NIC | `eth0` 3a:e4:08:af:95:9c, 152.53.177.26/22, mtu 1500 |
| **vLAN NIC** | **`eth1` 3a:e4:08:af:95:9d, mtu 1500, UP** — MAC matches inventory |
| Password auth | `PasswordAuthentication no` — delivery passwords are dead |
| netplan | present: `/etc/netplan/50-cloud-init.yaml` |

## The catalogue label is stale

netcup's flavour is named "Ubuntu 24.04.4 BIOS amd64", but the installed
system reports **24.04.5**. The flavour NAME lags the image CONTENT. So
selecting the newest flavour netcup lists does yield the newest point release
after all — the name simply cannot be trusted as the version of record.
Verify on the node, not from the catalogue string.

## MTU

vLAN interface `eth1` reports **mtu 1500** (device limits: minmtu 68,
maxmtu 65535). This is the INTERFACE MTU only. The end-to-end path MTU across
the netcup vLAN switch is still unverified — that needs a second node with a
vLAN address, which is Gate 3.

Hetzner's host 1400 / cilium_mtu 1360 must NOT be carried over: netcup's vLAN
presents 1500, 100 bytes more headroom, because it does not impose the
encapsulation overhead a Hetzner cloud network does.

## Two pieces of luck worth recording

1. The vLAN NIC is named **`eth1`** — exactly what Hetzner's kubevip role
   already expects (`kubevip_interface: "eth1"`). No change needed.
2. netcup's delivered netplan already contains an `eth1` stanza matching on
   **MAC address** with no addresses configured — the precise hook needed for
   the static vLAN address, and confirmation that MAC-matching (not interface
   naming) is the right approach on this platform.
