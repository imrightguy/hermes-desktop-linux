#!/usr/bin/env python3
"""Stamp, describe, and plan unofficial Linux desktop releases.

The workflow calls this after it has fetched an upstream GitHub release.
Stable tags only: semver (``v0.22.5``) or the older calver tags
(``v2026.8.16.2``). Pre-release tags such as ``v0.22.5+canary…`` are refused.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

# Stable upstream releases are semver (v0.22.5) or the older calver tags
# (v2026.9.24, v2026.8.16.2). Pre-release tags are not GitHub "latest"
# releases and are refused so they cannot be published.
_STABLE_TAG = re.compile(
    r"^v(?:\d+\.\d+\.\d+|\d{4}\.\d{1,2}\.\d{1,2}(?:\.\d+)?)$"
)
_PACKAGE_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
_RELEASE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RELEASE_VERSION = re.compile(
    r'(<release\s+version=")[^"]*("\s+date=")[^"]*("\s*/>)'
)
_SHA = re.compile(r"^[0-9a-f]{40}$")

UPSTREAM_REPOSITORY = "NousResearch/hermes-agent"


def normalize_release_tag(tag: str) -> str:
    """Return a stable release tag, or raise ValueError."""
    cleaned = tag.strip()
    if not _STABLE_TAG.fullmatch(cleaned):
        raise ValueError(
            f"refusing tag {tag!r}; expected a stable release such as v0.22.5"
        )
    return cleaned


def version_from_tag(tag: str) -> str:
    """Strip the leading v from a tag that already passed normalize_release_tag."""
    return normalize_release_tag(tag)[1:]


def decide_release(release: dict, requested: str = "") -> dict[str, str]:
    """Decide from an upstream release payload, before the local existence check.

    ``action`` is ``publish`` or ``error``. Skipping an existing local release
    is the caller's job, because that needs this repository's release list.
    """
    requested = (requested or "").strip()
    tag_name = str(release.get("tag_name") or "")
    if release.get("draft") is True or release.get("prerelease") is True:
        shown = requested or tag_name or "(unknown)"
        return {
            "action": "error",
            "tag": shown,
            "version": "",
            "reason": f"refusing {shown}: only stable upstream releases are published",
        }
    chosen = requested or tag_name
    try:
        tag = normalize_release_tag(chosen)
    except ValueError as exc:
        return {"action": "error", "tag": chosen, "version": "", "reason": str(exc)}
    if requested and tag_name and tag != tag_name:
        return {
            "action": "error",
            "tag": requested,
            "version": "",
            "reason": f"upstream release tag {tag_name} did not match requested {requested}",
        }
    return {
        "action": "publish",
        "tag": tag,
        "version": version_from_tag(tag),
        "reason": "stable upstream release",
    }


def stamp_package_version(desktop_dir: Path, version: str, release_date: str) -> None:
    """Write the release version into Snap and Flatpak metadata.

    Electron AppImage/deb/rpm versions are passed to electron-builder
    separately. These files are what Flatpak and Snap embed.
    """
    if not _PACKAGE_VERSION.fullmatch(version):
        raise ValueError(f"invalid package version {version!r}")
    if not _RELEASE_DATE.fullmatch(release_date):
        raise ValueError(f"invalid release date {release_date!r}")

    snapcraft = desktop_dir / "snap" / "snapcraft.yaml"
    _rewrite(
        snapcraft,
        lambda text: re.sub(
            r"(?m)^version:\s*.*$",
            f"version: '{version}'",
            text,
            count=1,
        ),
    )
    replacement = rf"\g<1>{version}\g<2>{release_date}\g<3>"
    for relative in (
        Path("flatpak") / "com.nousresearch.Hermes.metainfo.xml",
        Path("snap") / "gui" / "hermes-desktop.metainfo.xml",
    ):
        path = desktop_dir / relative
        _rewrite(
            path,
            lambda text, replacement=replacement: _RELEASE_VERSION.sub(
                replacement, text, count=1
            ),
        )


def release_notes(tag: str, upstream_sha: str, packaging_sha: str) -> str:
    """Release body for this repository's Linux desktop packages."""
    tag = normalize_release_tag(tag)
    if not _SHA.fullmatch(upstream_sha):
        raise ValueError(f"invalid upstream commit sha {upstream_sha!r}")
    if not _SHA.fullmatch(packaging_sha):
        raise ValueError(f"invalid packaging commit sha {packaging_sha!r}")
    version = version_from_tag(tag)
    return (
        f"Unofficial Linux desktop packages for Hermes Agent {tag} (x86_64).\n\n"
        "These builds are not published by Nous Research. "
        f"They were produced from `{UPSTREAM_REPOSITORY}@{upstream_sha}` "
        f"(tag `{tag}`) plus the packaging in this repository at `{packaging_sha}`.\n\n"
        f"- `Hermes-{version}-linux-x86_64.AppImage` — `chmod +x` and run\n"
        f"- `Hermes-{version}-linux-amd64.deb` — `sudo apt install ./Hermes-{version}-linux-amd64.deb`\n"
        f"- `Hermes-{version}-linux-x86_64.rpm` — `sudo dnf install ./Hermes-{version}-linux-x86_64.rpm`\n"
        f"- `Hermes-{version}-linux-x86_64.flatpak` — `flatpak install --user ./Hermes-{version}-linux-x86_64.flatpak`\n"
        "- Snap — `sudo snap install --dangerous --devmode ./hermes-desktop_*.snap` "
        "(the snap is built with devmode confinement)\n\n"
        f"Upstream release: https://github.com/{UPSTREAM_REPOSITORY}/releases/tag/{tag}\n"
    )


def failure_issue_title(tag: str) -> str:
    cleaned = tag.strip()
    if not cleaned:
        return "Linux packaging failed"
    return f"Linux packaging failed for {cleaned}"


def failure_issue_body(
    tag: str,
    run_url: str,
    reason: str,
    log_excerpt: str = "",
) -> str:
    """Issue body used when a patch or build fails. No release was published."""
    shown = tag.strip() or "(unknown)"
    lines = [
        f"Linux packaging failed for `{shown}`. No GitHub Release was published.",
        "",
        f"Run: {run_url}" if run_url else "Run URL was not available.",
        "",
        reason.strip() or "The workflow failed before it recorded a reason.",
        "",
        "What to do:",
        "- If a patch failed to apply, update `patches/` against this upstream tag and re-run the Linux desktop release workflow.",
        "- If a build failed, fix the packaging files and re-run the same workflow.",
        "- Set the workflow's version input to this tag. Leave dry run off to publish after the build succeeds.",
        "- Delete a partial release for this tag if one exists, then re-run. An existing release is skipped.",
        "",
    ]
    excerpt = log_excerpt.strip()
    if len(excerpt) > 12000:
        excerpt = excerpt[-12000:]
    if excerpt:
        lines.extend(["Log excerpt:", "", "```", excerpt, "```", ""])
    return "\n".join(lines)


def _rewrite(path: Path, transform) -> None:
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        raise ValueError(f"version stamp did not change {path}")
    path.write_text(updated, encoding="utf-8")


def _emit_output(pairs: dict[str, str]) -> None:
    for key, value in pairs.items():
        print(f"{key}={shlex.quote(value)}")


def _cmd_decide(args: argparse.Namespace) -> int:
    release = json.loads(Path(args.release_json).read_text(encoding="utf-8"))
    _emit_output(decide_release(release, requested=args.requested or ""))
    return 0


def _cmd_stamp(args: argparse.Namespace) -> int:
    stamp_package_version(Path(args.desktop), version_from_tag(args.tag), args.date)
    return 0


def _cmd_notes(args: argparse.Namespace) -> int:
    sys.stdout.write(
        release_notes(args.tag, args.upstream_sha, args.packaging_sha)
    )
    return 0


def _cmd_issue_body(args: argparse.Namespace) -> int:
    log_excerpt = ""
    if args.log_file:
        log_excerpt = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
    sys.stdout.write(
        failure_issue_body(
            args.tag or "",
            args.run_url or "",
            args.reason or "",
            log_excerpt,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    decide = sub.add_parser("decide")
    decide.add_argument("--release-json", required=True)
    decide.add_argument("--requested", default="")
    decide.set_defaults(func=_cmd_decide)

    stamp = sub.add_parser("stamp")
    stamp.add_argument("--desktop", required=True)
    stamp.add_argument("--tag", required=True)
    stamp.add_argument("--date", required=True)
    stamp.set_defaults(func=_cmd_stamp)

    notes = sub.add_parser("notes")
    notes.add_argument("--tag", required=True)
    notes.add_argument("--upstream-sha", required=True)
    notes.add_argument("--packaging-sha", required=True)
    notes.set_defaults(func=_cmd_notes)

    issue = sub.add_parser("issue-body")
    issue.add_argument("--tag", default="")
    issue.add_argument("--run-url", default="")
    issue.add_argument("--reason", default="")
    issue.add_argument("--log-file", default="")
    issue.set_defaults(func=_cmd_issue_body)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
