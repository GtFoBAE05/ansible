# Changelog

All notable changes to this role are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this role adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-26

### Added

- Built-in default site: `nginx_default_site` (default `true`) renders a
  catch-all `server { listen 80 default_server; }` into the built-in
  `nginx.conf`. It replaces the vendor default site the role's `nginx.conf`
  drops, so a fresh apply serves the **distro's stock welcome page** on `:80`
  just like a manual install — no vhost required. When
  `nginx_default_site_root` / `nginx_default_site_index` are left empty they
  resolve to the OS-family default (`/var/www/html` +
  `index.nginx-debian.html` on Debian, `/usr/share/nginx/html` + `index.html`
  on RHEL), matching where each package ships its welcome page; override them to
  serve your own content. `nginx_default_site_ipv6` (default `true`) toggles the
  `[::]:80` listener for IPv6-disabled hosts. Set `nginx_default_site: false`
  for reverse-proxy or strictly vhost-driven hosts. The document root is not
  created by the role. Validated in `assert`, documented, and covered
  end-to-end in the Molecule scenario.

## [1.0.0] - 2026-07-26

### Added

- Initial release.
- Install nginx from the distribution repositories by default (nginx ships in
  the base repos of every supported distro). `nginx_use_official_repo` opts in
  to nginx's own official repository (nginx.org) for newer builds — APT on the
  Debian family, a yum/dnf repo on the RHEL family — with a `stable`/`mainline`
  channel choice. Official-repo use on Fedora or an unknown OS is rejected at
  validation with a clear message.
- Optional version pinning (`nginx_version`).
- Main `nginx.conf` management with three sources — your own template
  (`nginx_config_template`), raw content (`nginx_config`), or a built-in default
  rendered from tunables (`worker_processes`, `worker_connections`,
  `keepalive_timeout`, `server_tokens`, `client_max_body_size`, `gzip`, plus raw
  `nginx_extra_conf_options` / `nginx_extra_http_options`) that includes
  `conf.d/*.conf`.
- Virtual hosts via `nginx_vhosts` written to `conf.d/<name>.conf`, with optional
  pruning (`nginx_prune_vhosts`) and vendor default-site removal
  (`nginx_remove_default_vhost`). The portable `conf.d` layout is used across all
  OS families rather than the Debian-only `sites-enabled` scheme.
- Production-grade hardening baked into the default `nginx.conf`:
  `worker_rlimit_nofile` (asserted ≥ `worker_connections`), slowloris client
  timeouts (`client_body_timeout`, `client_header_timeout`, `send_timeout`),
  `keepalive_requests`, `reset_timedout_connection`, and a default `charset`,
  plus an opt-in `open_file_cache` block — all exposed as tunables with safe,
  conservative defaults (no fragile lab values).
- Reusable best-practice snippets shipped to `/etc/nginx/snippets` and included
  per vhost with `include /etc/nginx/snippets/<name>.conf;`: `static-cache.conf` (long-lived
  static-asset caching) and `security-headers.conf` (baseline response headers),
  both tunable and individually disableable, plus arbitrary user fragments via
  `nginx_snippets`. Snippets are inert until included; only role-owned files are
  removed on teardown, never the shared `snippets/` directory or package-shipped
  fragments.
- Every `nginx.conf` write is validated with `nginx -t -c` before it is placed,
  and a full `nginx -t` gate runs after vhosts are deployed — a broken config
  never reaches a running server, which is then reloaded gracefully.
- `nginx_state: absent` stops and disables the service and removes role-managed
  vhosts, preserving web roots and `/var/log/nginx` by design.
- Molecule scenario across Ubuntu 24.04 and Rocky Linux 9 with idempotence and
  end-to-end HTTP verification.
