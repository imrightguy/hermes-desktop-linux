# hermes-desktop-linux

Unofficial Linux packages of [Hermes Desktop](https://github.com/NousResearch/hermes-agent), built whenever Nous Research publishes a stable `hermes-agent` release.

This repository is not a fork and it does not mirror upstream source. It holds the Linux packaging overlay (patches, Flatpak and Snap files, and the release workflow). Each release checks out the upstream tag, applies that overlay, and publishes the built packages here.

These packages are not published or supported by Nous Research. Hermes Agent is their project; this repository only repackages the desktop app for Linux.

## What gets published

For each stable upstream tag (the same tag name, for example `v0.22.5`):

| File | Use |
| --- | --- |
| `Hermes-<version>-linux-x86_64.AppImage` | `chmod +x` and run |
| `Hermes-<version>-linux-amd64.deb` | `sudo apt install ./Hermes-<version>-linux-amd64.deb` |
| `Hermes-<version>-linux-x86_64.rpm` | `sudo dnf install ./Hermes-<version>-linux-x86_64.rpm` |
| `Hermes-<version>-linux-x86_64.flatpak` | `flatpak install --user ./Hermes-<version>-linux-x86_64.flatpak` |
| `hermes-desktop_<version>_amd64.snap` | `sudo snap install --dangerous --devmode ./hermes-desktop_*_amd64.snap` |

Packages are x86_64 only. The snap is built with `confinement: devmode`, so it is installed with `--dangerous --devmode` and is not a confined store snap. The Flatpak is a single-file bundle from this release, not a Flathub build.

The desktop app is the Electron client. The Hermes CLI, configuration, and state stay in the normal `~/.hermes` install on the host.

## How releases are made

[`.github/workflows/linux-release.yml`](.github/workflows/linux-release.yml) runs on GitHub-hosted `ubuntu-latest` runners.

- **Schedule:** every day at 09:17 UTC (`17 9 * * *`).
- **Manual:** Actions → Linux desktop release → Run workflow.
  - `version`: upstream stable tag to build. Leave it empty to use [`NousResearch/hermes-agent` releases/latest](https://github.com/NousResearch/hermes-agent/releases/latest), which is the latest non-prerelease release.
  - `dry_run`: build the packages and skip creating the GitHub Release.

The workflow:

1. Reads the upstream stable release and refuses drafts and pre-releases.
2. Skips the run when this repository already has a release with that tag.
3. Clones `NousResearch/hermes-agent` at that tag.
4. Applies `patches/*.patch` with `git apply --3way`, then copies `packaging/` into the tree. The first patch that does not apply fails the run.
5. Builds the AppImage, `.deb`, and `.rpm`, then the Flatpak and the snap from the unpacked app.
6. Publishes a GitHub Release on **this** repository with the upstream tag and attaches every artifact.

It uses the default `GITHUB_TOKEN` (`contents: write` to create the release, `issues: write` to file a failure). No personal access token is required, because nothing is pushed back to the upstream project.

If a patch fails to apply or any build fails, the workflow does not publish. It opens an issue titled `Linux packaging failed for <tag>`, or updates that issue if it is already open. Fix the overlay and re-run the workflow with the version input set to that tag. Delete a partial release for the tag first if one was created; an existing tag is skipped.

The packaging patch was taken from the Linux desktop work on `imrightguy/hermes-agent` branch `cursor/upstream-linux-release-8885`, rebased onto upstream `v0.22.5` (Flatpak, Snap, and AppImage packaging, plus the CommonJS icon-tool fix and the electron-builder artifact names). It keeps applying to newer stable tags until upstream edits one of the patched files. Snap stage packages use the Ubuntu 24.04 names `libgtk-3-0t64` and `libatspi2.0-0t64`, which are what current GitHub runners and the `core24` base provide.

## First run

Scheduled runs start only after this workflow file is on the default branch. After merging:

1. Open the **Actions** tab and enable Actions if GitHub has them turned off.
2. Enable **Issues** so a failed build can be recorded.
3. Run the workflow once by hand. Leave the version empty to publish the current stable release, or turn on dry run to build without publishing.

No repository secret is required.
