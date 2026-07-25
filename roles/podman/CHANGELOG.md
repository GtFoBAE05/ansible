# Changelog

All notable changes to the `podman` role are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this role
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-25

### Added

- Initial release.
- OS-agnostic Podman installation via the `package` module, with OS-family task
  files (`install-Debian.yml`, `install-RedHat.yml`, `install-default.yml`) and
  variable files loaded through `first_found`.
- Optional version pinning through `podman_version`.
- Rootless prerequisites: `passt` (pasta), `slirp4netns`, `fuse-overlayfs` and
  the OS-appropriate uid-mapping package.
- Explicit `/etc/subuid` and `/etc/subgid` management for pre-existing accounts
  via `usermod --add-subuids/--add-subgids`, with a non-overlapping allocator
  and `podman system migrate` on change.
- Quadlet support verification against a configurable minimum Podman version
  (4.4).
- Optional management of `registries.conf` and the rootless network backend.
- systemd linger management for rootless service accounts.
- Granular tags: `podman`, `podman-install`, `podman-verify`, `podman-config`,
  `podman-rootless`, `podman-validate`.
- `podman_parse_subid` filter plugin for parsing subordinate ID files.
