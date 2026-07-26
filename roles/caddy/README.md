# caddy

Installs the [Caddy](https://caddyserver.com/) web server from its **official
package repository** and manages the Caddyfile and systemd service.

- Debian/Ubuntu → official Cloudsmith APT repo (`stable` or `testing`).
- RHEL/Rocky/Alma/Fedora → official COPR `@caddy/caddy` (via
  `community.general.copr`).

There is no Caddy package in the base archives of the supported distros, so the
official repo is enabled by default. The role validates every Caddyfile with
`caddy validate` **before** placing it and then reloads gracefully, so a broken
config never reaches a running server.

## Requirements

- A systemd-based target (the role asserts this).
- Collections: `community.general` (COPR). See the repo-root `requirements.yml`.
- Ansible ≥ 2.14.

## Supported platforms

| OS family | Distros tested | Repo source |
|---|---|---|
| Debian | Ubuntu 22.04 / 24.04, Debian 12 | Cloudsmith APT |
| RedHat | Rocky/Alma/RHEL 9 (EL8/10, Fedora expected) | COPR `@caddy/caddy` |

## Role variables

### State & installation

| Variable | Default | Description |
|---|---|---|
| `caddy_state` | `present` | `present` or `absent`. |
| `caddy_use_official_repo` | `true` | Configure the official repo. Set false only if a source is already present. |
| `caddy_repo_channel` | `stable` | Debian channel: `stable` or `testing`. |
| `caddy_copr_project` | `@caddy/caddy` | COPR project on the RedHat family. |
| `caddy_version` | `""` | Pin an exact package version, e.g. `2.8.4`. Empty = repo latest. |
| `caddy_package_state` | `present` | `present` or `latest` (ignored when a version is pinned). |

### Service

| Variable | Default | Description |
|---|---|---|
| `caddy_service_enabled` | `true` | Enable at boot. |
| `caddy_service_state` | `started` | `started`, `stopped`, or `reloaded`. When `stopped`, reload/restart handlers are skipped. |

### Configuration

| Variable | Default | Description |
|---|---|---|
| `caddy_manage_config` | `true` | Manage `/etc/caddy/Caddyfile`. |
| `caddy_config_backup` | `true` | Back up the Caddyfile on change. |
| `caddy_config_template` | `""` | Path to **your** Jinja2 template (highest priority). |
| `caddy_config` | `""` | Raw Caddyfile content as a string. |
| `caddy_email` | `""` | ACME email for the default Caddyfile's global block. |
| `caddy_global_options` | `""` | Extra global-options lines for the default Caddyfile (one directive per line). |
| `caddy_config_snippets` | `{}` | `name: {content: ...}` snippets written to `conf.d/<name>.caddy` and imported. |
| `caddy_manage_snippets_dir` | `true` | Create/manage `conf.d`. |
| `caddy_prune_snippets` | `false` | Delete `conf.d/*.caddy` files not in `caddy_config_snippets`. |
| `caddy_environment` | `{}` | `VAR: value` env for the service (EnvironmentFile + drop-in). Change ⇒ restart. |

### Teardown

| Variable | Default | Description |
|---|---|---|
| `caddy_remove_package` | `false` | On `absent`, also uninstall the package. |

`caddy_config_template` and `caddy_config` are mutually exclusive; setting both
fails validation. If neither is set, the role renders a minimal default
Caddyfile from `caddy_email` + `caddy_global_options` that imports every snippet.

## Usage

Minimal — reverse-proxy one site with automatic HTTPS:

```yaml
- hosts: web
  become: true
  roles:
    - role: caddy
      vars:
        caddy_email: ops@example.com
        caddy_config_snippets:
          app:
            content: |
              app.example.com {
                reverse_proxy localhost:8080
              }
```

Bring your own full Caddyfile template:

```yaml
- role: caddy
  vars:
    caddy_config_template: "{{ playbook_dir }}/files/Caddyfile.j2"
```

DNS-01 ACME with a Cloudflare token (custom build with the DNS plugin assumed):

```yaml
- role: caddy
  vars:
    caddy_environment:
      CF_API_TOKEN: "{{ vault_cf_api_token }}"
    caddy_global_options: |
      acme_dns cloudflare {env.CF_API_TOKEN}
    caddy_config_snippets:
      app:
        content: |
          app.example.com {
            reverse_proxy localhost:8080
          }
```

## Tags

`caddy-validate`, `caddy-install`, `caddy-config`, `caddy-service`,
`caddy-absent`. Example: `--tags caddy-config` re-renders and reloads config
only.

## Verification & troubleshooting

```bash
systemctl status caddy
caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile
journalctl -u caddy -e
curl -I http://localhost/
```

| Symptom | Cause | Fix |
|---|---|---|
| Task fails at `validate:` on a config task | Caddyfile syntax error | Fix the offending `caddy_config*`/snippet; the bad file is never installed. |
| `System has not been booted with systemd` | Non-systemd host (or a container without a real init) | Use a systemd host; in Molecule keep `override_command: false`. |
| Repo key download fails | No egress to `dl.cloudsmith.io` | Mirror the repo internally and set `caddy_use_official_repo: false`. |
| COPR enable fails on EL | dnf copr plugin missing / no egress | Ensure `dnf-plugins-core` installs and the host can reach COPR. |
| Env var not picked up | Reload does not re-read unit env | The role restarts on env change; confirm the drop-in exists under `/etc/systemd/system/caddy.service.d/`. |
| Certificates gone after re-provision | — | They are not: `absent` preserves `/var/lib/caddy`. |

## Removal

`caddy_state: absent` stops/disables the service and removes managed config.
Certificates and state under `/var/lib/caddy` are **preserved** on purpose.
For a full teardown:

```bash
ansible ... -e caddy_state=absent -e caddy_remove_package=true
rm -rf /var/lib/caddy   # only if you really want to discard certificates
```

## Versioning

- **MAJOR** — renaming/retyping a variable, changing the Caddyfile/snippets
  layout in a way that orphans existing deployments, dropping an OS family.
- **MINOR** — new optional variables, new distro support, new tagged blocks.
- **PATCH** — idempotency/check-mode fixes, package-name corrections, template
  and permission fixes.

## License

MIT
