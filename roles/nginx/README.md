# nginx

Installs the [nginx](https://nginx.org/) web server and manages `nginx.conf`,
virtual hosts, and the systemd service.

- By default nginx is installed from the **distribution's own repositories** —
  it ships in the base repos of every supported distro, so no third-party repo
  is needed.
- Optionally (`nginx_use_official_repo: true`) the role configures nginx's
  **official repository** (nginx.org) for newer `stable`/`mainline` builds:
  APT on the Debian family, a yum/dnf repo on the RHEL family.

Virtual hosts are managed as `conf.d/*.conf` — the portable layout every distro
includes — not the Debian-only `sites-enabled` scheme, so vhosts behave
identically across OS families. The role validates `nginx.conf` with `nginx -t`
**before** placing it and runs a full `nginx -t` gate before reloading, so a
broken config never reaches a running server.

## Requirements

- A systemd-based target (the role asserts this).
- Ansible ≥ 2.14. No extra collections are required (uses `ansible.builtin` only).

## Supported platforms

| OS family | Distros tested | Default source | Official repo |
|---|---|---|---|
| Debian | Ubuntu 22.04 / 24.04, Debian 12 | distro `nginx` | nginx.org APT |
| RedHat | Rocky/Alma/RHEL 9 (EL8/10 expected) | distro `nginx` | nginx.org yum |
| Fedora | current | distro `nginx` | ❌ not published by nginx.org |

## Role variables

### State & installation

| Variable | Default | Description |
|---|---|---|
| `nginx_state` | `present` | `present` or `absent`. |
| `nginx_use_official_repo` | `false` | Configure the nginx.org official repo instead of using the distro package. |
| `nginx_repo_channel` | `stable` | Official-repo branch: `stable` or `mainline`. |
| `nginx_version` | `""` | Pin an exact package version, e.g. `1.26.2`. Empty = repo latest. |
| `nginx_package_state` | `present` | `present` or `latest` (ignored when a version is pinned). |

### Service

| Variable | Default | Description |
|---|---|---|
| `nginx_service_enabled` | `true` | Enable at boot. |
| `nginx_service_state` | `started` | `started`, `stopped`, or `reloaded`. When `stopped`, the reload handler is skipped. |

### Main configuration

| Variable | Default | Description |
|---|---|---|
| `nginx_manage_config` | `true` | Manage `/etc/nginx/nginx.conf`. |
| `nginx_config_backup` | `true` | Back up `nginx.conf` on change. |
| `nginx_config_template` | `""` | Path to **your** Jinja2 template (highest priority). |
| `nginx_config` | `""` | Raw `nginx.conf` content as a string. |

`nginx_config_template` and `nginx_config` are mutually exclusive; setting both
fails validation. If neither is set, the role renders a default `nginx.conf`
from the tunables below that includes every vhost in `conf.d`.

### Default `nginx.conf` tunables

_(ignored when `nginx_config_template` or `nginx_config` is set)_

| Variable | Default | Description |
|---|---|---|
| `nginx_user` | `""` | `user` directive. Empty ⇒ OS default (`www-data` on Debian, `nginx` on RHEL). |
| `nginx_worker_processes` | `auto` | `worker_processes`. |
| `nginx_worker_connections` | `1024` | `worker_connections`. |
| `nginx_worker_rlimit_nofile` | `65535` | Max FDs per worker. Must be ≥ `worker_connections` (asserted) **and** ≤ the OS hard nofile limit — lower it on FD-capped hosts. |
| `nginx_keepalive_timeout` | `65` | `keepalive_timeout`. |
| `nginx_keepalive_requests` | `1000` | Requests served per kept-alive connection. |
| `nginx_client_body_timeout` | `30s` | Slowloris hardening — client body read timeout. |
| `nginx_client_header_timeout` | `30s` | Slowloris hardening — client header read timeout. |
| `nginx_send_timeout` | `30s` | Timeout for transmitting a response to the client. |
| `nginx_reset_timedout_connection` | `on` | Free memory/sockets of connections closed on timeout. |
| `nginx_charset` | `utf-8` | Default charset for text responses. Empty disables the directive. |
| `nginx_open_file_cache` | `""` | Opt-in static-FD cache, e.g. `max=10000 inactive=20s`. Empty = off (workload-dependent). |
| `nginx_open_file_cache_valid` | `30s` | Revalidation interval (only when the cache is enabled). |
| `nginx_open_file_cache_min_uses` | `2` | Min accesses before an entry is cached (only when enabled). |
| `nginx_open_file_cache_errors` | `on` | Cache lookup errors too (only when enabled). |
| `nginx_server_tokens` | `off` | Hide the nginx version in responses. |
| `nginx_client_max_body_size` | `1m` | `client_max_body_size`. |
| `nginx_gzip` | `true` | Enable `gzip on`. |
| `nginx_error_log_level` | `warn` | `error_log` severity. |
| `nginx_extra_conf_options` | `""` | Raw lines injected into the main context (one directive per line). |
| `nginx_extra_http_options` | `""` | Raw lines injected into the `http` block (one directive per line). |

### Virtual hosts

| Variable | Default | Description |
|---|---|---|
| `nginx_vhosts` | `{}` | `name: {content: ...}` server blocks written to `conf.d/<name>.conf`. |
| `nginx_manage_vhost_dir` | `true` | Create/manage `conf.d`. |
| `nginx_prune_vhosts` | `false` | Delete `conf.d/*.conf` files not in `nginx_vhosts`. |
| `nginx_remove_default_vhost` | `false` | Remove the vendor default site (`conf.d/default.conf`, Debian `sites-enabled/default`). |

### Built-in default site

The role's `nginx.conf` includes only `conf.d/*.conf`, not Debian's
`sites-enabled/`, so without a listener nothing answers `:80` — nginx runs but
every request is refused. To avoid that surprise the role ships a catch-all
default site **on by default** that points at the package's own web root, so a
fresh apply serves the **distro's stock welcome page** on `:80`, just like a
manual install. Turn it **off** for reverse-proxy or strictly vhost-driven
hosts, where a `default_server` would shadow the sites you actually define.

When `nginx_default_site_root`/`_index` are left empty the role uses the
OS-family default — `/var/www/html` + `index.nginx-debian.html` on Debian,
`/usr/share/nginx/html` + `index.html` on RHEL — which is exactly where each
package ships its welcome page. Override them to serve your own content.

| Variable | Default | Description |
|---|---|---|
| `nginx_default_site` | `true` | Render a catch-all `server { listen 80 default_server; }` into the built-in `nginx.conf`. Set `false` to disable. Ignored when `nginx_config_template`/`nginx_config` is set. |
| `nginx_default_site_root` | `""` (OS default) | Document root served. Empty → the package web root (`/var/www/html` Debian, `/usr/share/nginx/html` RHEL). **The role does not create it.** |
| `nginx_default_site_index` | `""` (OS default) | `index` filenames. Empty → the OS default, including the distro's stock welcome file. |
| `nginx_default_site_ipv6` | `true` | Also `listen [::]:80`. Set `false` where IPv6 is disabled, else nginx fails to bind at start. |

> Do not combine `nginx_default_site` with a vhost that also declares
> `listen 80 default_server` — two default servers on one port fail `nginx -t`.

### Reusable snippets

The role ships best-practice fragments to `/etc/nginx/snippets`. A snippet is
inert until a server block `include`s it, so shipping one costs nothing until you
opt in per vhost with `include /etc/nginx/snippets/<name>.conf;`. This keeps you
writing plain, readable server blocks while the repeated boilerplate —
static-asset caching, security headers — lives in one reviewed place.

> **Use the absolute path** (`/etc/nginx/snippets/…`), not the relative
> `snippets/…`. The role validates each `nginx.conf` with `nginx -t` from a temp
> directory before installing it; nginx resolves *relative* includes against the
> config file's own directory, so a relative snippet path would fail that
> pre-check. Absolute paths resolve identically at validate time and at runtime.

| Variable | Default | Description |
|---|---|---|
| `nginx_manage_snippets` | `true` | Manage the `snippets/` directory and role-owned fragments. |
| `nginx_static_cache_snippet` | `true` | Ship `static-cache.conf` (long-lived caching for static assets). |
| `nginx_static_cache_extensions` | `jpg\|jpeg\|png\|gif\|ico\|css\|js\|svg\|woff\|woff2\|ttf\|eot` | Extensions the cache location matches. |
| `nginx_static_cache_expires` | `30d` | `expires` for matched assets. |
| `nginx_static_cache_control` | `public, no-transform` | `Cache-Control` header value. |
| `nginx_security_headers_snippet` | `true` | Ship `security-headers.conf`. |
| `nginx_security_headers` | `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin` | Headers emitted (with `always`). |
| `nginx_snippets` | `{}` | Your own `name: {content: ...}` fragments written to `snippets/<name>.conf`. |

Only role-owned files (the built-in snippets plus your `nginx_snippets` keys) are
removed on teardown or when disabled — the shared `snippets/` directory and any
package-shipped fragments (e.g. Debian's `fastcgi-php.conf`) are left untouched.

### Teardown

| Variable | Default | Description |
|---|---|---|
| `nginx_remove_package` | `false` | On `absent`, also uninstall the package. |

## Usage

Minimal — serve one site (distro package):

```yaml
- hosts: web
  become: true
  roles:
    - role: nginx
      vars:
        nginx_remove_default_vhost: true
        nginx_vhosts:
          app:
            content: |
              server {
                  listen 80;
                  server_name app.example.com;
                  root /var/www/app;
                  index index.html;
              }
```

Best-practice static site — a clean server block that pulls the repeated
boilerplate in from snippets:

```yaml
- role: nginx
  vars:
    nginx_remove_default_vhost: true
    nginx_vhosts:
      app:
        content: |
          server {
              listen 80;
              server_name app.example.com;
              root /var/www/app;
              index index.html;

              # Long-lived caching for static assets + baseline security headers.
              include /etc/nginx/snippets/static-cache.conf;
              include /etc/nginx/snippets/security-headers.conf;

              location / {
                  try_files $uri $uri/ =404;
              }
          }
```

(`server_tokens off` and `client_max_body_size` are set once in the `http` block
of the rendered `nginx.conf`, so every server block inherits them — no need to
repeat them per vhost.)

Reverse proxy, on the nginx.org mainline branch:

```yaml
- role: nginx
  vars:
    nginx_use_official_repo: true
    nginx_repo_channel: mainline
    nginx_remove_default_vhost: true
    nginx_vhosts:
      proxy:
        content: |
          server {
              listen 80;
              server_name app.example.com;
              location / {
                  proxy_pass http://127.0.0.1:8080;
                  proxy_set_header Host $host;
                  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
              }
          }
```

Bring your own full `nginx.conf`:

```yaml
- role: nginx
  vars:
    nginx_config_template: "{{ playbook_dir }}/files/nginx.conf.j2"
```

## Tags

`nginx-validate`, `nginx-install`, `nginx-config`, `nginx-service`,
`nginx-absent`. Example: `--tags nginx-config` re-renders config and vhosts and
reloads only.

## Verification & troubleshooting

```bash
systemctl status nginx
nginx -t
journalctl -u nginx -e
curl -I http://localhost/
```

| Symptom | Cause | Fix |
|---|---|---|
| Task fails at `validate:` deploying `nginx.conf` | Syntax error in the main config | Fix `nginx_config*`/tunables; the bad file is never installed. |
| Task fails at **Validate the full nginx configuration** | A vhost in `nginx_vhosts` is invalid | Fix the offending vhost. The reload is skipped, so the running server keeps its previous config; the bad file stays on disk until the next good run. |
| `System has not been booted with systemd` | Non-systemd host (or a container without a real init) | Use a systemd host; in Molecule keep `override_command: false`. |
| nginx runs but `curl http://host/` gives `Connection refused` and `ss -tlnp` shows nothing on `:80` | No server block listens on `:80` — `nginx_default_site` was disabled and no `nginx_vhosts` define a `listen 80;` | Re-enable `nginx_default_site`, or add a vhost with `listen 80;`. |
| `curl http://host/` connects but returns `403`/`404` | Default site points at a web root with no matching `index` file (e.g. you overrode `nginx_default_site_root` to an empty dir) | Put an index file in the root, or add its name to `nginx_default_site_index`. The role does not create the web root. |
| `nginx: [emerg] bind() to [::]:80 failed` at start | Default site tries the IPv6 wildcard on an IPv6-disabled host | Set `nginx_default_site_ipv6: false`. |
| Port 80 already answered by a default page | Vendor default site still enabled | Set `nginx_remove_default_vhost: true`. |
| Official repo enable fails | No egress to `nginx.org` | Mirror the repo internally, or leave `nginx_use_official_repo: false` to use the distro package. |
| `nginx_use_official_repo` rejected on Fedora | nginx.org publishes no Fedora packages | Use the Fedora package (`nginx_use_official_repo: false`). |

## Removal

`nginx_state: absent` stops/disables the service and removes role-managed
vhosts. Web roots and `/var/log/nginx` are **preserved** on purpose. For a
fuller teardown:

```yaml
ansible ... -e nginx_state=absent -e nginx_remove_package=true
```

## Versioning

- **MAJOR** — renaming/retyping a variable, changing the `nginx.conf`/vhost
  layout in a way that orphans existing deployments, dropping an OS family.
- **MINOR** — new optional variables, new distro support, new tagged blocks.
- **PATCH** — idempotency/check-mode fixes, package-name corrections, template
  and permission fixes.

## License

MIT
