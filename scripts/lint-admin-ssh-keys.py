#!/usr/bin/env python3
"""Fail closed when production admin SSH keys are unsafe or mislabelled."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import re
import struct
import sys
from pathlib import Path

import yaml

INVENTORY_VARS = Path("ansible/inventory/production/group_vars/all.yml")
BREAK_GLASS_COMMENT = re.compile(r"^veridex-breakglass-[0-9]{8}$")
PRIMARY_COMMENT = "veridex-netcup-prod"


def ed25519_material(encoded: str) -> bytes:
    """Decode and structurally validate an OpenSSH Ed25519 public-key blob."""
    material = base64.b64decode(encoded, validate=True)
    offset = 0

    def field() -> bytes:
        nonlocal offset
        if offset + 4 > len(material):
            raise ValueError("truncated SSH field length")
        length = struct.unpack(">I", material[offset : offset + 4])[0]
        offset += 4
        if offset + length > len(material):
            raise ValueError("truncated SSH field")
        value = material[offset : offset + length]
        offset += length
        return value

    if field() != b"ssh-ed25519":
        raise ValueError("key blob algorithm is not ssh-ed25519")
    if len(field()) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    if offset != len(material):
        raise ValueError("unexpected trailing SSH key data")
    return material


def validate(keys: object) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    fingerprints: list[str] = []
    if not isinstance(keys, list) or len(keys) < 2:
        return ["admin_ssh_public_keys must contain at least two keys"], fingerprints

    materials: list[bytes] = []
    comments: list[str] = []
    for index, entry in enumerate(keys):
        label = f"admin_ssh_public_keys[{index}]"
        if not isinstance(entry, str):
            errors.append(f"{label} must be a string")
            continue
        fields = entry.split()
        if len(fields) < 3:
            errors.append(f"{label} must contain an algorithm, key, and comment")
            continue
        algorithm, encoded, comment = fields[0], fields[1], fields[2]
        if algorithm != "ssh-ed25519":
            errors.append(f"{label} must use ssh-ed25519")
        try:
            material = ed25519_material(encoded)
        except (binascii.Error, ValueError) as exc:
            errors.append(f"{label} has invalid Ed25519 key material ({exc})")
            continue
        materials.append(material)
        comments.append(comment)
        digest = base64.b64encode(hashlib.sha256(material).digest()).decode().rstrip("=")
        fingerprints.append(f"{comment}: SHA256:{digest}")

    if len(materials) != len(set(materials)):
        errors.append("admin SSH keys must have unique key material, regardless of comments")
    if comments.count(PRIMARY_COMMENT) != 1:
        errors.append(f"exactly one key must be named {PRIMARY_COMMENT}")
    if not any(BREAK_GLASS_COMMENT.fullmatch(comment) for comment in comments):
        errors.append("at least one key must be named veridex-breakglass-YYYYMMDD")
    return errors, fingerprints


def self_test() -> list[str]:
    def key_blob(byte: int) -> str:
        algorithm = b"ssh-ed25519"
        public = bytes([byte]) * 32
        blob = struct.pack(">I", len(algorithm)) + algorithm
        blob += struct.pack(">I", len(public)) + public
        return base64.b64encode(blob).decode()

    key_a = key_blob(1)
    key_b = key_blob(2)
    valid = [
        f"ssh-ed25519 {key_a} {PRIMARY_COMMENT}",
        f"ssh-ed25519 {key_b} veridex-breakglass-20260913",
    ]
    cases = {
        "valid distinct keys": (valid, True),
        "one key": (valid[:1], False),
        "duplicate same comment": ([valid[0], valid[0]], False),
        "duplicate different comment": (
            [valid[0], f"ssh-ed25519 {key_a} veridex-breakglass-20260913"],
            False,
        ),
        "malformed key": ([valid[0], "ssh-ed25519 !!! veridex-breakglass-20260913"], False),
        "missing emergency designation": (
            [valid[0], f"ssh-ed25519 {key_b} ordinary-key"],
            False,
        ),
    }
    failures = []
    for name, (keys, should_pass) in cases.items():
        passed = not validate(keys)[0]
        if passed != should_pass:
            failures.append(f"self-test {name!r} unexpectedly {'passed' if passed else 'failed'}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        if failures:
            print("\n".join(f"ERROR: {failure}" for failure in failures))
            return 1
        print("Admin SSH key validator self-tests: PASS")
        return 0

    path = Path(args.root).resolve() / INVENTORY_VARS
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: {INVENTORY_VARS}: cannot be read ({exc.__class__.__name__})")
        return 1
    errors, fingerprints = validate((document or {}).get("admin_ssh_public_keys"))
    for fingerprint in fingerprints:
        print(fingerprint)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("Production admin SSH keys: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
