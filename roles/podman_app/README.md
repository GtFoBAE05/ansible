# Role: `podman_app`

Deploys **one** containerized application per invocation as a rootless Podman
[Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
`.container` unit, running under a dedicated service account.

`podman generate systemd` is deprecated upstream ("We recommend using Quadlet
files when running Podman containers or pods under systemd… It will receive
urgent bug fixes but no new features"), so this role writes Quadlet units only.

## Design

- **One account per app.** A system account with no login shell and no password
  is created per application. The container never runs as root, and never as the
  `ansible` connection user.
- **Two-layer `become`.** `become: true` (root) provisions the account, data
  directories and linger. `become_user: <app account>` with `XDG_RUNTIME_DIR`
  set runs everything touching Quadlet and `systemctl --user`.
- **Fail fast.** `tasks/assert.yml` validates every required and enumerated
  variable before any change is made.
- **Reuses `podman`'s documented interface.** Subordinate ID provisioning is
  delegated to `podman`'s `tasks/rootless.yml`, a supported public entry point
  (see [podman's README](../podman/README.md#public-interface-tasksrootlessyml)),
  not an internal detail this role reaches into.

## Requirements

- The [`podman`](../podman/README.md) role, declared as a `meta` dependency and
  applied automatically.
- `containers.podman` collection (for `podman_image`).
- Podman >= 4.4 on the target host.

## Role variables

### Required

| Variable | Description |
| --- | --- |
| `podman_app_name` | Unique app name. Becomes the account name and the systemd unit `<name>.service`. Lowercase, `[a-z0-9_-]`, max 32 chars. |
| `podman_app_image` | Fully qualified image including registry and tag or digest. Short names are rejected. |

### Service account

| Variable | Default | Description |
| --- | --- | --- |
| `podman_app_user` | `{{ podman_app_name }}` | Service account name. |
| `podman_app_group` | `{{ podman_app_user }}` | Primary group. |
| `podman_app_home` | `/var/lib/{{ podman_app_user }}` | Home directory; holds the Quadlet unit. |
| `podman_app_shell` | `/usr/sbin/nologin` | Login shell. |
| `podman_app_system_user` | `true` | Create as a system account. |
| `podman_app_subuid_start` | `""` | Explicit subuid start. Auto-allocated when empty. |
| `podman_app_subid_count` | `65536` | Size of the subordinate ID range. |

### Container

| Variable | Default | Description |
| --- | --- | --- |
| `podman_app_ports` | `[]` | `PublishPort=` entries, e.g. `"127.0.0.1:8080:80"`. |
| `podman_app_volumes` | `[]` | `Volume=` entries, e.g. `"/var/lib/app/data:/data:Z"`. |
| `podman_app_directories` | `[]` | Host dirs to create, `[{path, mode, owner, group}]`. |
| `podman_app_env` | `{}` | Environment variables. |
| `podman_app_secret_env` | `{}` | Secret env vars; forces unit file mode `0600`. Supply via Vault. |
| `podman_app_container_options` | `[]` | Raw extra lines for the `[Container]` section. |
| `podman_app_command` | `""` | Overrides the image command (`Exec=`). |
| `podman_app_entrypoint` | `""` | Overrides the image entrypoint. |
| `podman_app_network` | `""` | Quadlet `Network=` value. |
| `podman_app_hostname` | `""` | Container hostname. |
| `podman_app_run_uid` / `_gid` | `""` | UID/GID inside the user namespace. |

### Resource limits

Requires cgroups v2 with `cpu` and `memory` delegated to the user slice
(default on EL9+ and Ubuntu 22.04+).

| Variable | Default | Description |
| --- | --- | --- |
| `podman_app_memory_limit` | `""` | e.g. `512m`. |
| `podman_app_memory_swap_limit` | `""` | e.g. `1g`. |
| `podman_app_cpu_quota` | `""` | e.g. `1.5`. |
| `podman_app_pids_limit` | `""` | e.g. `512`. |

### Health check

| Variable | Default |
| --- | --- |
| `podman_app_healthcheck_command` | `""` (disabled) |
| `podman_app_healthcheck_interval` | `30s` |
| `podman_app_healthcheck_retries` | `3` |
| `podman_app_healthcheck_start_period` | `10s` |
| `podman_app_healthcheck_timeout` | `5s` |

### systemd and lifecycle

| Variable | Default | Description |
| --- | --- | --- |
| `podman_app_restart_policy` | `always` | Any systemd `Restart=` value. |
| `podman_app_restart_sec` | `10` | Delay before restart. |
| `podman_app_timeout_start_sec` | `300` | Start timeout; raise for slow image pulls. |
| `podman_app_wanted_by` | `default.target` | `[Install] WantedBy=`. |
| `podman_app_autoupdate` | `registry` | `registry`, `local`, or `""` to disable. |
| `podman_app_enable_autoupdate_timer` | `false` | Enable `podman-auto-update.timer` for the account. |
| `podman_app_pull_image` | `true` | Pull during the Ansible run. |
| `podman_app_service_enabled` | `true` | Enable the unit at boot. |
| `podman_app_service_state` | `started` | Desired service state. |
| `podman_app_restart_on_change` | `true` | Restart when the unit file changes. |
| `podman_app_state` | `present` | `present` or `absent`. |

## Usage: two apps on one host

`allow_duplicates: true` in `meta/main.yml` lets the role be applied more than
once per play. With `roles:` blocks:

```yaml
- hosts: container_hosts
  roles:
    - role: podman_app
      vars:
        podman_app_name: web
        podman_app_image: docker.io/library/nginx:1.27-alpine
        podman_app_ports:
          - "127.0.0.1:8080:80"
        podman_app_memory_limit: 256m

    - role: podman_app
      vars:
        podman_app_name: api
        podman_app_image: registry.example.com/team/api:2.3.1
        podman_app_ports:
          - "127.0.0.1:9000:9000"
        podman_app_env:
          LOG_LEVEL: info
        podman_app_secret_env:
          DATABASE_URL: "{{ vault_api_database_url }}"
        podman_app_memory_limit: 1g
```

This produces two independent service accounts (`web`, `api`), two subuid
ranges, two Quadlet units and two user services — `web.service` under user `web`
and `api.service` under user `api`.

Equivalent with `include_role`, which also allows looping:

```yaml
- name: Deploy all applications
  ansible.builtin.include_role:
    name: podman_app
  vars:
    podman_app_name: "{{ item.name }}"
    podman_app_image: "{{ item.image }}"
    podman_app_ports: "{{ item.ports | default([]) }}"
  loop: "{{ podman_applications }}"
  loop_control:
    label: "{{ item.name }}"
```

## Verification and troubleshooting

Every user-scoped command needs `XDG_RUNTIME_DIR`, because `sudo`/`become` does
not create a login session:

```bash
APP=web
UID_APP=$(id -u "$APP")
run() { sudo -u "$APP" XDG_RUNTIME_DIR=/run/user/$UID_APP "$@"; }

run systemctl --user status "$APP.service"
run journalctl --user -u "$APP.service" -n 100 --no-pager
run podman ps -a
run podman logs "$APP"

# Inspect the generated unit
cat /var/lib/$APP/.config/containers/systemd/$APP.container
run systemctl --user cat "$APP.service"

# Apply unit changes by hand
run systemctl --user daemon-reload && run systemctl --user restart "$APP.service"
```

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Unit <app>.service not found` | Quadlet did not generate the unit | Check Podman >= 4.4, unit path, then `systemctl --user daemon-reload`. |
| `Failed to connect to bus` | `XDG_RUNTIME_DIR` unset or linger off | Export it; confirm `loginctl show-user <app> --property=Linger`. |
| Service stops after deploy | Container exits immediately | `podman logs <app>`; check `podman_app_command`. |
| Permission denied on a volume | SELinux label | Append `:Z` to the volume on EL hosts. |
| `bind: permission denied` | Rootless port < 1024 | Publish a high port, or lower `net.ipv4.ip_unprivileged_port_start`. |
| Image pull fails | Registry auth | Pre-place `auth.json` in the account's `~/.config/containers/`. |

## Removal

Setting `podman_app_state: absent` stops and disables the service, removes the
Quadlet unit and disables linger. It **deliberately leaves the service account,
its home directory and all application data in place** — deleting data as a side
effect of a state flag is destructive and hard to undo. Remove those manually
once you have confirmed the data is no longer needed:

```bash
sudo userdel -r web    # destroys /var/lib/web and its contents
```

## Versioning

Semantic versioning; see [CHANGELOG.md](CHANGELOG.md).

- **MAJOR** — renaming or changing the type of any `podman_app_*` variable,
  changing the unit file layout or the service naming scheme (both of which
  orphan units deployed by an earlier version), changing the default service
  account naming, or dropping an OS family.
- **MINOR** — new optional variables (additional Quadlet keys, new limits),
  support for a new distribution, new tagged blocks.
- **PATCH** — template fixes, idempotency and check-mode fixes, corrected
  assertion messages, permission fixes.
