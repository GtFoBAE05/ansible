# Changelog

All notable changes to the `podman_app` role are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this role
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-25

### Added

- Initial release.
- Rootless single-application deployment via a Quadlet `.container` unit written
  to `~/.config/containers/systemd/` of a dedicated per-app service account.
- Dedicated system account per application: no login shell, locked password,
  home under `/var/lib/<app>`.
- Two-layer `become` model — root for account, directory and linger
  provisioning; `become_user` with `XDG_RUNTIME_DIR` for all Quadlet and
  `systemctl --user` operations.
- Fail-fast validation of required and enumerated variables, including rejection
  of unqualified image names and of `AutoUpdate=registry` on digest-pinned
  images.
- Full parameterization: ports, volumes, managed data directories, environment
  and secret environment variables, command and entrypoint overrides, network,
  hostname, in-namespace UID/GID, memory/CPU/PID limits, health checks, restart
  policy and autoupdate policy.
- `allow_duplicates: true` and a `meta` dependency on the `podman` role, so the
  role can be applied once per application on a single host.
- Idempotent removal path via `podman_app_state: absent`, which preserves the
  service account and application data by design.
- Granular tags: `podman-app`, `podman-app-validate`, `podman-app-user`,
  `podman-app-quadlet`, `podman-app-service`, `podman-app-remove`.
