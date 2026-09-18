#!/usr/bin/env python3
"""Compare the live netcup provider firewall against the ruleset in Git.

READ-ONLY. This script issues GET requests only. It never PUTs, never fixes
drift, and never prints a token. Correcting drift is a deliberate operator
action, because the write path runs against an API netcup does not support.

    python3 scripts/verify-provider-firewall.py            # report
    python3 scripts/verify-provider-firewall.py --json     # machine-readable

Exit codes: 0 = live state matches Git, 1 = drift or missing rules, 2 = the
check could not run (no credential, API unreachable, schema moved).

Why exit 2 is separate: "I could not check" must never be mistaken for "no
drift". CI cannot run this without an SCP credential, so this is an
operator/periodic check rather than a CI gate -- adding it to CI would mean
storing a netcup credential in GitHub, which is a new secret and a new risk
for a check that is advisory by nature.

Source of truth: docs/security/provider-firewall-rules.yml
Rationale and costs: docs/security/provider-firewall.md
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
RULES = REPO / "docs" / "security" / "provider-firewall-rules.yml"
TOKEN_CACHE = pathlib.Path.home() / ".config" / "veridex" / "netcup-refresh-token"

# Fields compared per rule. Deliberately not every field the API returns:
# numberOfEffectiveRules is derived, and description is documentation.
COMPARED = ("direction", "protocol", "action", "destinationPorts")


def load_discover():
    """Reuse netcup-discover.py's auth and request helpers rather than
    re-implementing the OIDC device flow a second time."""
    spec = importlib.util.spec_from_file_location(
        "nd", REPO / "scripts" / "netcup-discover.py")
    nd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nd)
    return nd


def rule_key(rule: dict) -> tuple:
    return tuple(str(rule.get(f) or "") for f in COMPARED)


def describe(rule: dict) -> str:
    ports = rule.get("destinationPorts") or "-"
    return (f"{rule.get('direction','?')} {rule.get('protocol','?')} "
            f"{rule.get('action','?')} ports={ports}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    try:
        import yaml  # noqa: PLC0415 - optional dependency, reported clearly
    except ImportError:
        print("cannot check: PyYAML is not installed "
              "(pip install -r scripts/requirements-lint.txt)", file=sys.stderr)
        return 2

    if not RULES.exists():
        print(f"cannot check: {RULES} is missing", file=sys.stderr)
        return 2
    intent = yaml.safe_load(RULES.read_text(encoding="utf-8"))

    if not TOKEN_CACHE.exists():
        print("cannot check: no netcup credential available; this check is "
              "operator-run, not CI", file=sys.stderr)
        return 2

    nd = load_discover()
    try:
        token = nd.authenticate(TOKEN_CACHE)
    except Exception as exc:  # noqa: BLE001 - any auth failure is "cannot check"
        print(f"cannot check: authentication failed ({exc})", file=sys.stderr)
        return 2

    findings: list[str] = []
    report: dict = {"servers": {}, "drift": False}

    for sid, meta in intent["servers"].items():
        node, role = meta["node"], meta["role"]
        expected = list(intent["ingress"]["common"]) + list(
            intent["ingress"].get(role) or [])
        want = {rule_key(r) for r in expected}

        try:
            interfaces = nd.api_get(f"/servers/{sid}/interfaces", token) or []
        except Exception as exc:  # noqa: BLE001
            print(f"cannot check {node}: {exc}", file=sys.stderr)
            return 2

        public = [i for i in interfaces if i.get("ipv4")]
        if not public:
            findings.append(f"{node}: no public interface found")
            continue

        for iface in public:
            fw = nd.api_get(
                f"/servers/{sid}/interfaces/{iface['mac']}/firewall", token) or {}
            live_rules = [r for p in (fw.get("userPolicies") or [])
                          for r in (p.get("rules") or [])]
            have = {rule_key(r) for r in live_rules}

            missing = want - have
            extra = have - want
            copied = {p.get("name") for p in (fw.get("copiedPolicies") or [])}
            lost_copied = set(intent["expected_copied_policies"]) - copied
            implicit = fw.get("ingressImplicitRule")
            want_implicit = intent["ingress"]["implicit_rule"]

            entry = {
                "active": fw.get("active"),
                "ingress_implicit": implicit,
                "missing": sorted(" ".join(k) for k in missing),
                "unexpected": sorted(" ".join(k) for k in extra),
                "lost_netcup_policies": sorted(lost_copied),
            }
            report["servers"][node] = entry

            if not fw.get("active"):
                findings.append(f"{node}: firewall is INACTIVE")
            if implicit and implicit != want_implicit:
                findings.append(
                    f"{node}: ingress implicit rule is {implicit}, "
                    f"expected {want_implicit} -- unlisted ports are reachable")
            for r in expected:
                if rule_key(r) in missing:
                    findings.append(f"{node}: MISSING  {describe(r)}")
            for r in live_rules:
                if rule_key(r) in extra:
                    findings.append(f"{node}: UNEXPECTED {describe(r)}")
            for name in sorted(lost_copied):
                findings.append(f"{node}: netcup policy '{name}' is no longer attached")

    report["drift"] = bool(findings)

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        for line in findings:
            print(line)
        print()
        print(f"checked {len(report['servers'])} public interfaces against {RULES.name}")
        print("DRIFT" if findings else "live provider firewall matches Git")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
