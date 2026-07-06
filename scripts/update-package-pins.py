#!/usr/bin/env python3
"""Update extension package pins from apt-cache policy output."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "extensions.json"
GENERATOR = ROOT / "scripts" / "generate-containerfile.py"
PGDG_SOURCE = "pgdg"


@dataclass
class PinUpdate:
    extension_id: str
    package: str
    source: str
    enabled: bool
    before: str
    after: str


@dataclass
class MissingPackage:
    extension_id: str
    package: str
    source: str
    enabled: bool


def render_package_name(package_template: str, postgres_major: int) -> str:
    return package_template.replace("${PKG_PREFIX}", f"postgresql-{postgres_major}")


def run_policy_probe(manifest: dict[str, Any], packages: list[str]) -> dict[str, str]:
    pigsty = next(source for source in manifest["aptSources"] if source["name"] == "pigsty")
    package_list = " ".join(packages)
    script = f"""
apt-get update >/dev/null
apt-get install -y curl ca-certificates gnupg >/dev/null
mkdir -p /etc/apt/keyrings
curl -fsSL {pigsty["keyUrl"]} | gpg --dearmor -o /etc/apt/keyrings/pigsty.gpg
echo {json.dumps(pigsty["aptLine"])} > /etc/apt/sources.list.d/pigsty-io.list
apt-get update >/dev/null
for pkg in {package_list}; do
  printf '\036%s\n' "$pkg"
  apt-cache policy "$pkg"
done
"""

    result = subprocess.run(
        [
            "podman",
            "run",
            "--rm",
            "--user",
            "0",
            "--platform",
            "linux/amd64",
            manifest["baseImage"],
            "sh",
            "-ceu",
            script,
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)

    policies: dict[str, str] = {}
    for chunk in result.stdout.split("\036"):
        chunk = chunk.strip()
        if not chunk:
            continue
        package, _, policy = chunk.partition("\n")
        policies[package] = policy
    return policies


def latest_version_for_source(policy: str, origin_pattern: str) -> str | None:
    versions: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None

    for line in policy.splitlines():
        version_match = re.match(r"\s+(?:\*\*\*)?\s*([^\s]+)\s+\d+", line)
        if version_match:
            current = (version_match.group(1), [])
            versions.append(current)
            continue

        if current is not None and origin_pattern in line:
            current[1].append(line.strip())

    for version, origins in versions:
        if origins:
            return version
    return None


def update_manifest(manifest: dict[str, Any]) -> tuple[list[PinUpdate], list[MissingPackage]]:
    sources = {source["name"]: source for source in manifest["aptSources"]}
    postgres_major = int(manifest["postgresMajor"])
    package_names = [
        render_package_name(extension["package"], postgres_major)
        for extension in manifest["extensions"]
    ]
    policies = run_policy_probe(manifest, package_names)

    updates: list[PinUpdate] = []
    missing: list[MissingPackage] = []

    for extension in manifest["extensions"]:
        package_name = render_package_name(extension["package"], postgres_major)
        source_name = extension["source"]
        source = sources[source_name]
        latest = latest_version_for_source(policies.get(package_name, ""), source["originPattern"])

        if latest is None:
            missing.append(
                MissingPackage(
                    extension_id=extension["id"],
                    package=package_name,
                    source=source_name,
                    enabled=bool(extension["enabled"]),
                )
            )
            continue

        if latest != extension["version"]:
            updates.append(
                PinUpdate(
                    extension_id=extension["id"],
                    package=package_name,
                    source=source_name,
                    enabled=bool(extension["enabled"]),
                    before=extension["version"],
                    after=latest,
                )
            )
            extension["version"] = latest

    return updates, missing


def render_summary(updates: list[PinUpdate], missing: list[MissingPackage]) -> str:
    enabled_updates = [update for update in updates if update.enabled]
    disabled_updates = [update for update in updates if not update.enabled]
    enabled_missing = [item for item in missing if item.enabled]
    disabled_missing = [item for item in missing if not item.enabled]

    lines = ["# PostgreSQL Extension Package Pin Update", ""]
    if updates:
        lines.extend(["Updated package pins from apt-cache policy output.", ""])
    else:
        lines.extend(["No package pin updates were found.", ""])

    if enabled_updates:
        lines.extend(["## Enabled package updates", ""])
        for update in enabled_updates:
            lines.append(
                f"- `{update.extension_id}` (`{update.package}`, {update.source}): "
                f"`{update.before}` -> `{update.after}`"
            )
        lines.append("")

    if disabled_updates:
        lines.extend(["## Disabled package pin refreshes", ""])
        for update in disabled_updates:
            lines.append(
                f"- `{update.extension_id}` (`{update.package}`, {update.source}): "
                f"`{update.before}` -> `{update.after}`"
            )
        lines.append("")

    if disabled_missing:
        lines.extend(["## Disabled packages not found", ""])
        for item in disabled_missing:
            lines.append(f"- `{item.extension_id}` (`{item.package}`, {item.source})")
        lines.append("")

    if enabled_missing:
        lines.extend(["## Enabled packages not found", ""])
        for item in enabled_missing:
            lines.append(f"- `{item.extension_id}` (`{item.package}`, {item.source})")
        lines.append("")

    lines.extend(
        [
            "## Verification",
            "",
            "- `python3 scripts/generate-containerfile.py`",
            "- `python3 -m json.tool extensions.json`",
            "- `python3 -m py_compile scripts/*.py`",
            "- `podman build --platform linux/amd64 --file images/Containerfile.extensions --tag ghcr.io/supafull/supabase-extensions:update-check .`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report updates without editing files")
    parser.add_argument("--summary", type=Path, help="Write a Markdown summary for update PRs")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    updates, missing = update_manifest(manifest)
    enabled_missing = [item for item in missing if item.enabled]

    summary = render_summary(updates, missing)
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(summary)
    else:
        print(summary)

    if enabled_missing:
        sys.stderr.write("Enabled packages were not found in their declared source.\n")
        raise SystemExit(1)

    if updates and not args.dry_run:
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
