# Changelog

All notable changes to this role are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this role adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-25

### Added

- Initial release.
- Install Caddy from the official package repository: Cloudsmith APT (`stable`
  or `testing` channel) on the Debian family, COPR `@caddy/caddy` on the RHEL
  family. `caddy_use_official_repo` toggles repo automation off for hosts that
  already have a source configured.
- Optional version pinning (`caddy_version`).
- Caddyfile management with three sources — your own template
  (`caddy_config_template`), raw content (`caddy_config`), or a built-in default
  that renders a global options block and imports `conf.d/*.caddy`.
- Site snippets via `caddy_config_snippets` with optional pruning
  (`caddy_prune_snippets`).
- Every Caddyfile write is validated with `caddy validate` before it is placed,
  then a graceful `systemctl reload` is triggered — a broken config never
  reaches a running server.
- Environment file + systemd drop-in from `caddy_environment` (for ACME
  DNS-challenge credentials); changes trigger a restart, not a reload.
- `caddy_state: absent` stops and disables the service and removes managed
  config, preserving `/var/lib/caddy` (certificates) by design.
- Molecule scenario across Ubuntu 24.04 and Rocky Linux 9 with idempotence and
  end-to-end HTTP verification.
