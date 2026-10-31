#!/usr/bin/env python3
"""Unit tests for release planning, stamping, and failure issues."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from release_metadata import (
    decide_release,
    failure_issue_body,
    failure_issue_title,
    normalize_release_tag,
    release_notes,
    stamp_package_version,
    version_from_tag,
)


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


class ReleaseMetadataTest(unittest.TestCase):
    def test_stable_tags_and_refused_prereleases(self) -> None:
        self.assertEqual(normalize_release_tag("v0.22.5"), "v0.22.5")
        self.assertEqual(version_from_tag("v2026.8.16.2"), "2026.8.16.2")
        with self.assertRaises(ValueError):
            normalize_release_tag("v0.22.5+canary.20261030T064851Z")
        with self.assertRaises(ValueError):
            normalize_release_tag("0.22.5")

    def test_decide_accepts_latest_stable_release(self) -> None:
        decision = decide_release(
            {"tag_name": "v0.22.5", "draft": False, "prerelease": False}
        )
        self.assertEqual(decision["action"], "publish")
        self.assertEqual(decision["tag"], "v0.22.5")
        self.assertEqual(decision["version"], "0.22.5")

    def test_decide_refuses_prerelease_and_draft(self) -> None:
        prerelease = decide_release(
            {
                "tag_name": "v0.22.5+canary.20261030T064851Z",
                "draft": False,
                "prerelease": True,
            }
        )
        self.assertEqual(prerelease["action"], "error")
        draft = decide_release(
            {"tag_name": "v0.22.5", "draft": True, "prerelease": False}
        )
        self.assertEqual(draft["action"], "error")

    def test_stamp_rewrites_snap_and_flatpak_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp)
            (desktop / "snap" / "gui").mkdir(parents=True)
            (desktop / "flatpak").mkdir()
            (desktop / "snap" / "snapcraft.yaml").write_text(
                "name: hermes\nversion: '0.0.0'\nbase: core24\n",
                encoding="utf-8",
            )
            release = '<release version="0.0.0" date="2026-08-31"/>'
            for path in (
                desktop / "flatpak" / "com.nousresearch.Hermes.metainfo.xml",
                desktop / "snap" / "gui" / "hermes-desktop.metainfo.xml",
            ):
                path.write_text(
                    f"<releases>\n    {release}\n</releases>\n",
                    encoding="utf-8",
                )

            stamp_package_version(desktop, "0.22.5", "2026-10-23")

            snapcraft = (desktop / "snap" / "snapcraft.yaml").read_text(encoding="utf-8")
            self.assertIn("version: '0.22.5'", snapcraft)
            for path in (
                desktop / "flatpak" / "com.nousresearch.Hermes.metainfo.xml",
                desktop / "snap" / "gui" / "hermes-desktop.metainfo.xml",
            ):
                text = path.read_text(encoding="utf-8")
                self.assertIn('version="0.22.5"', text)
                self.assertIn('date="2026-10-23"', text)

    def test_stamp_matches_packaged_metadata_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp)
            for relative in (
                "snap/snapcraft.yaml",
                "snap/gui/hermes-desktop.metainfo.xml",
                "flatpak/com.nousresearch.Hermes.metainfo.xml",
            ):
                source = ROOT / "packaging" / "apps" / "desktop" / relative
                destination = desktop / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            stamp_package_version(desktop, "0.22.5", "2026-10-31")
            self.assertIn(
                "version: '0.22.5'",
                (desktop / "snap" / "snapcraft.yaml").read_text(encoding="utf-8"),
            )

    def test_notes_name_packages_and_both_shas(self) -> None:
        notes = release_notes("v0.22.5", SHA, "b" * 40)
        self.assertIn("Unofficial Linux desktop packages", notes)
        self.assertIn("Hermes-0.22.5-linux-x86_64.AppImage", notes)
        self.assertIn("Hermes-0.22.5-linux-amd64.deb", notes)
        self.assertIn("Hermes-0.22.5-linux-x86_64.rpm", notes)
        self.assertIn(SHA, notes)
        self.assertIn("b" * 40, notes)
        self.assertIn("not published by Nous Research", notes)

    def test_failure_issue_names_the_tag(self) -> None:
        self.assertEqual(
            failure_issue_title("v0.22.5"),
            "Linux packaging failed for v0.22.5",
        )
        self.assertEqual(failure_issue_title("  "), "Linux packaging failed")
        body = failure_issue_body(
            "v0.22.5",
            "https://github.com/example/repo/actions/runs/1",
            "git apply --3way failed on patches/0001-linux-desktop-packaging.patch",
        )
        self.assertIn("v0.22.5", body)
        self.assertIn("No GitHub Release was published", body)
        self.assertIn("git apply --3way failed", body)

    def test_cli_decide_prints_shell_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "release.json"
            payload.write_text(
                json.dumps(
                    {"tag_name": "v0.22.5", "draft": False, "prerelease": False}
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts" / "release_metadata.py"),
                    "decide",
                    "--release-json",
                    str(payload),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertIn("action=publish", completed.stdout)
        self.assertIn("tag=v0.22.5", completed.stdout)
        self.assertIn("version=0.22.5", completed.stdout)


if __name__ == "__main__":
    unittest.main()
