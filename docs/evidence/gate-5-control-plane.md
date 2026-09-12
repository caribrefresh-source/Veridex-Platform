# Gate 5 — k3s HA control plane

Executed 2026-09-12. Three servers bootstrapped with embedded etcd.

    NAME               STATUS     ROLES                VERSION        INTERNAL-IP
    veridex-server-1   NotReady   control-plane,etcd   v1.36.4+k3s1   10.2.1.10
    veridex-server-2   NotReady   control-plane,etcd   v1.36.4+k3s1   10.2.1.11
    veridex-server-3   NotReady   control-plane,etcd   v1.36.4+k3s1   10.2.1.12

    EtcdIsVoter=True on all three.

`NotReady` is the CORRECT state here: kubelet reports "cni plugin not
initialized" because Cilium is not installed yet. EXTERNAL-IP is <none> and
INTERNAL-IP is the vLAN address on all three, confirming cluster traffic is
bound to the private network rather than the public interface.

## Decisions verifiable in the live node args

  --cluster-cidr 10.44.0.0/16  --service-cidr 10.45.0.0/16
      distinct from Hetzner's 10.42/10.43, preserving Cilium ClusterMesh
  --flannel-backend none  --disable-kube-proxy  --disable-network-policy
      Cilium owns networking
  --disable-cloud-controller, and NO cloud-provider=external
      netcup has no CCM. Setting cloud-provider=external would taint every
      node node.cloudprovider.kubernetes.io/uninitialized with nothing
      present to clear it, and nothing would ever schedule
  --tls-san 10.2.0.100
      the kube-vip VIP, so the API certificate is valid for it before the
      VIP itself exists
  --secrets-encryption, --etcd-snapshot-schedule-cron "0 * * * *",
  --etcd-snapshot-retention 48
      at-rest encryption; hourly snapshots for the RPO <= 1h target
  allocatable cpu 3 of 4
      system-reserved and kube-reserved applied

## etcd S3 deliberately not enabled

The template emits the etcd-s3 block only when endpoint AND access key AND
secret key are all non-empty. On the Hetzner cluster the equivalent condition
tested only the endpoint -- a hardcoded literal, therefore always truthy --
so etcd-s3 ran with blank credentials, every upload failed, and the bucket
was empty for months with nothing surfacing it. Failing loud (the block is
visibly absent from the rendered config) beats uploading nowhere.

## What Hetzner needs here and this cluster does not

The Hetzner role re-inserts TWELVE iptables ACCEPT rules after k3s starts,
because k3s installs rules that shadow per-port ones. This cluster's firewall
trusts the whole 10.2.0.0/16 vLAN in a single nftables rule, so none of that
is needed -- the control plane came up with no firewall intervention.

## Bugs found and fixed during this gate

1. systemd drop-in written before `k3s.service.d` existed, guarded by a
   `when: ... is failed` that can never run, because the failing task aborts
   the play. Directory creation moved ahead of the write.
2. Assertion used jsonpath `[?(@.type=="InternalIP")]`. The nested double
   quotes do not survive Ansible's command module, so the filter failed and
   the task dumped the entire node object. Replaced with a membership check
   over all addresses -- equivalent, no quoting hazard.

## Idempotence

The run that joined servers 2 and 3 included server-1, already bootstrapped:

    veridex-server-1  ok=17  changed=0
    veridex-server-2  ok=19  changed=7
    veridex-server-3  ok=19  changed=7

## Secret handling

The cluster token is generated locally, stored at ~/.config/veridex/k3s-token
mode 600, and passed via the K3S_TOKEN environment variable. It is not in the
repository. For CI it must be added as the GitHub secret K3S_TOKEN.
