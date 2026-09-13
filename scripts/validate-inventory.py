#!/usr/bin/env python3
"""Validate the Ansible inventory against schemas/inventory.schema.json.

Why this exists
---------------
Gate 0 of the cluster plan requires that the inventory identifies only the
five netcup nodes. A file that parses is not enough for that: a sixth host, a
duplicated address, a node outside the vLAN register, or an identity quietly
overridden somewhere Ansible also reads all parse cleanly and fail later,
against real machines.

Checks
------
Schema (schemas/inventory.schema.json):
  exactly three k3s_servers and two k3s_agents, named veridex-server-N /
  veridex-agent-N, each carrying ansible_host, private_ip, vlan_mac,
  netcup_server_id and node_index with the right types, and nothing else.

Cross-field (not expressible in JSON Schema):
  - every public address, private address, MAC and netcup server id is unique
  - node_index matches the number in the host name
  - k3s_bootstrap is set on exactly the first server in sorted order, because
    the roles bootstrap groups['k3s_servers'] | sort | first and never read
    the flag
  - ansible_host is a public address; private_ip is inside both
    private_network_cidr and private_node_allocation_block from group_vars
  - kubevip_vip is inside private_network_cidr, outside the node allocation
    block, and is not any node's address

Identity is defined in one place:
  - no group_vars or host_vars file anywhere under ansible/ (inventories or
    playbooks) sets ansible_host, ansible_ssh_host, private_ip, vlan_mac,
    netcup_server_id, node_index or k3s_bootstrap
  - no file sits directly under ansible/inventory/, and each environment holds
    only hosts.yml, group_vars/ and host_vars/
  - every other environment's hosts.yml parses as a YAML mapping and declares
    no hosts; host_vars exist only for the five production nodes

Addresses are read from the inventory, never hardcoded here.

Usage
-----
    python3 scripts/validate-inventory.py [--root .]
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ANSIBLE_ROOT = Path("ansible")
INVENTORY_ROOT = ANSIBLE_ROOT / "inventory"
PRODUCTION = INVENTORY_ROOT / "production"
SCHEMA = Path("schemas/inventory.schema.json")
GROUPS = ("k3s_servers", "k3s_agents")
NAME_RE = re.compile(r"^veridex-(?:server|agent)-(\d+)$")
UNIQUE_KEYS = ("ansible_host", "private_ip", "vlan_mac", "netcup_server_id")
IDENTITY_KEYS = frozenset({
    "ansible_host", "ansible_ssh_host", "private_ip", "vlan_mac",
    "netcup_server_id", "node_index", "k3s_bootstrap",
})
ALLOWED_INVENTORY_ENTRIES = {"hosts.yml", "group_vars", "host_vars"}
VARS_DIRS = {"group_vars", "host_vars"}
VARS_SUFFIXES = ("", ".yml", ".yaml", ".json")


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def hosts_in(inventory) -> dict[str, dict]:
    """Every host under any group, however deeply nested."""
    found: dict[str, dict] = {}

    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        for name, host_vars in (node.get("hosts") or {}).items():
            found[name] = host_vars or {}
        for child in (node.get("children") or {}).values():
            walk(child)

    if isinstance(inventory, dict):
        for top in inventory.values():
            walk(top)
    return found


def report(errors: list[str], summary: str) -> int:
    for err in errors:
        print(f"ERROR: {err}")
    print()
    if errors:
        print(f"inventory validation failed: {len(errors)} error(s)")
        return 1
    print(summary)
    return 0


def check_identity_overrides(root: Path, known_hosts: set[str], errors: list[str]) -> None:
    ansible_root = root / ANSIBLE_ROOT
    for path in sorted(ansible_root.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        parents = set(path.relative_to(ansible_root).parts[:-1])
        if not parents & VARS_DIRS or path.suffix not in VARS_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if "host_vars" in parents and path.stem not in known_hosts:
            errors.append(f"{rel}: host_vars for a host that is not one of the five production nodes")
        try:
            data = load_yaml(path)
        except yaml.YAMLError:
            errors.append(f"{rel}: does not parse as YAML")
            continue
        if isinstance(data, dict):
            overridden = sorted(IDENTITY_KEYS & {str(key) for key in data})
            if overridden:
                errors.append(
                    f"{rel}: sets {', '.join(overridden)}; node identity is defined only in "
                    f"{PRODUCTION.as_posix()}/hosts.yml"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the netcup Ansible inventory.")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    hosts_file = root / PRODUCTION / "hosts.yml"
    vars_file = root / PRODUCTION / "group_vars" / "all.yml"
    schema_file = root / SCHEMA

    missing = [f for f in (hosts_file, vars_file, schema_file) if not f.is_file()]
    if missing:
        return report([f"missing {f.relative_to(root).as_posix()}" for f in missing], "")

    errors: list[str] = []
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    inventory = load_yaml(hosts_file)
    for err in sorted(validator.iter_errors(inventory), key=lambda e: list(map(str, e.absolute_path))):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"schema: {where}: {err.message}")
    if errors:
        # Cross-field checks assume the shape the schema guarantees.
        return report(errors, "")

    group_vars = load_yaml(vars_file) or {}
    try:
        network = ipaddress.ip_network(group_vars["private_network_cidr"])
        node_block = ipaddress.ip_network(group_vars["private_node_allocation_block"])
        vip = ipaddress.ip_address(group_vars["kubevip_vip"])
    except (KeyError, TypeError, ValueError) as exc:
        return report(
            [f"group_vars/all.yml: private_network_cidr, private_node_allocation_block "
             f"and kubevip_vip must all be present and valid ({exc!r})"],
            "",
        )

    if not node_block.subnet_of(network):
        errors.append(f"private_node_allocation_block {node_block} is outside private_network_cidr {network}")
    if vip not in network:
        errors.append(f"kubevip_vip {vip} is outside private_network_cidr {network}")
    if vip in node_block:
        errors.append(f"kubevip_vip {vip} is inside the node allocation block {node_block}")

    children = inventory["all"]["children"]
    seen: dict[str, dict[str, str]] = {key: {} for key in UNIQUE_KEYS}
    bootstraps: list[str] = []
    counts: dict[str, int] = {}

    for group in GROUPS:
        group_hosts = children[group]["hosts"]
        counts[group] = len(group_hosts)
        for name, host in group_hosts.items():
            number = NAME_RE.match(name)
            if number and int(number.group(1)) != host["node_index"]:
                errors.append(f"{name}: node_index {host['node_index']} does not match the host name")

            for key in UNIQUE_KEYS:
                value = str(host[key]).lower()
                if value in seen[key]:
                    errors.append(f"{name}: {key} {host[key]} duplicates {seen[key][value]}")
                else:
                    seen[key][value] = name

            public = ipaddress.ip_address(host["ansible_host"])
            private = ipaddress.ip_address(host["private_ip"])
            if not public.is_global:
                errors.append(f"{name}: ansible_host {public} is not a public address")
            if private not in network:
                errors.append(f"{name}: private_ip {private} is outside private_network_cidr {network}")
            elif private not in node_block:
                errors.append(f"{name}: private_ip {private} is outside the node allocation block {node_block}")
            if private == vip:
                errors.append(f"{name}: private_ip {private} is the kube-vip VIP")

            if host.get("k3s_bootstrap") is True:
                bootstraps.append(f"{group}/{name}")

    first_server = sorted(children["k3s_servers"]["hosts"])[0]
    if bootstraps != [f"k3s_servers/{first_server}"]:
        errors.append(
            f"k3s_bootstrap must be set on exactly one host, {first_server}: the roles bootstrap "
            f"groups['k3s_servers'] | sort | first and never read the flag; found {bootstraps or 'none'}"
        )

    known_hosts = set(hosts_in(inventory))
    check_identity_overrides(root, known_hosts, errors)

    inventory_root = root / INVENTORY_ROOT
    other_inventories = 0
    for entry in sorted(inventory_root.iterdir()):
        rel_entry = entry.relative_to(root).as_posix()
        if entry.is_file():
            if entry.name != ".gitkeep":
                errors.append(f"{rel_entry}: file directly under {INVENTORY_ROOT.as_posix()}/ -- "
                              "Ansible can read it as an inventory source")
            continue
        for item in sorted(entry.iterdir()):
            if item.name not in ALLOWED_INVENTORY_ENTRIES:
                errors.append(
                    f"{item.relative_to(root).as_posix()}: unexpected inventory source; "
                    "only hosts.yml, group_vars/ and host_vars/ are allowed"
                )
        if entry.resolve() == (root / PRODUCTION).resolve():
            continue
        env_hosts = entry / "hosts.yml"
        if not env_hosts.is_file():
            continue
        other_inventories += 1
        try:
            data = load_yaml(env_hosts)
        except yaml.YAMLError:
            errors.append(f"{rel_entry}/hosts.yml: does not parse as YAML")
            continue
        if data is not None and not isinstance(data, dict):
            errors.append(
                f"{rel_entry}/hosts.yml: does not parse as a YAML mapping; Ansible may read it "
                "as an INI inventory instead"
            )
            continue
        extra = hosts_in(data)
        if extra:
            errors.append(
                f"{rel_entry}/hosts.yml declares {len(extra)} host(s) ({', '.join(sorted(extra))}); "
                "only the five production netcup nodes may be inventoried"
            )

    summary = (
        f"inventory valid: {sum(counts.values())} hosts "
        f"({counts['k3s_servers']} k3s_servers, {counts['k3s_agents']} k3s_agents) "
        f"against {SCHEMA.as_posix()}; bootstrap server {first_server}; "
        f"{other_inventories} other inventory file(s) declare no hosts"
    )
    return report(errors, summary)


if __name__ == "__main__":
    sys.exit(main())
