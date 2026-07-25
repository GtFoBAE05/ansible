# Role: `podman`

Installs Podman and prepares a host for **rootless** container workloads. It
deploys no containers — it stops once Podman is ready. Application deployment is
the job of the [`podman_app`](../podman/../podman_app/README.md) role, which
declares this role as a dependency.

## What it does

1. Asserts the host runs systemd and that `podman_rootless_users` is well formed.
2. Loads OS-family variables from `vars/{Debian,RedHat,default}.yml`.
3. Installs Podman and the rootless prerequisites (`passt`/`slirp4netns`,
   `fuse-overlayfs`, `uidmap`/`shadow-utils`).
4. Verifies the installed Podman is new enough for Quadlet (>= 4.4).
5. Optionally manages `registries.conf` and the rootless network backend.
6. Explicitly assigns `/etc/subuid` and `/etc/subgid` ranges and enables linger.

## Requirements

- Ansible >= 2.14, connecting as a non-root sudo user with `become: true`.
- A systemd host: Ubuntu 22.04/24.04 or EL 9/10.
- `community.general` collection (only when `podman_manage_containers_conf` is
  enabled — it uses `ini_file`).

> **Ubuntu 22.04 caveat:** the jammy archive ships Podman 3.4.4, which predates
> Quadlet (added in 4.4). On a stock 22.04 host the Quadlet assertion fails by
> design, because `podman_app` cannot work there. Options:
>
> 1. Point `podman_enable_extra_repo` at a repository carrying Podman >= 4.4
>    (see below). Recommended.
> 2. Set `podman_assert_quadlet_support: false` to install Podman 3.4 anyway.
>    The `podman` role succeeds, but `podman_app` will not work.
> 3. Use Ubuntu 24.04 or EL 9/10, which need no extra repository.
>
> **Do not use the old Kubic `devel:kubic:libcontainers` repository.** It is
> unmaintained — upstream now directs users to distro packages, and the repo has
> not been updated in years.

## Role variables

All variables below live in `defaults/main.yml` and are safe to override.

### Installation

| Variable | Default | Description |
| --- | --- | --- |
| `podman_version` | `""` | Exact package version to pin. Empty installs the distro's latest. |
| `podman_package_state` | `present` | Package state when no version is pinned. Use `latest` to always upgrade. |
| `podman_install_rootless_prereqs` | `true` | Install the rootless prerequisite packages. |
| `podman_install_pasta` | `true` | Install `passt`, the default rootless backend since Podman 5.0. |
| `podman_install_slirp4netns` | `true` | Install `slirp4netns`, the default on Podman 4.x. |
| `podman_min_version_quadlet` | `"4.4"` | Minimum version required for Quadlet. |
| `podman_assert_quadlet_support` | `true` | Fail the run when Podman is older than the minimum. |

### Extra APT repository (Debian family only)

Needed only where the distro archive is too old for Quadlet, in practice Ubuntu
22.04. Disabled by default — you must supply the repository yourself.

| Variable | Default | Description |
| --- | --- | --- |
| `podman_enable_extra_repo` | `false` | Enable the extra repository. |
| `podman_extra_repo_url` | `""` | Repository base URL. Required when enabled. |
| `podman_extra_repo_key_url` | `""` | Signing key URL. Required when enabled. |
| `podman_extra_repo_keyring_path` | `/etc/apt/keyrings/podman-extra.gpg` | Where the key is stored. |
| `podman_extra_repo_suite` | `""` | Suite. Leave empty for a flat repository. |
| `podman_extra_repo_components` | `/` | Components, or `/` for a flat repository. |
| `podman_extra_repo_pin_priority` | `600` | APT pin priority. |
| `podman_extra_repo_pin_packages` | Podman + container stack | Packages the repo is allowed to supply. |

The repository is pinned so it can only provide Podman and its container stack,
not override unrelated packages from the Ubuntu archive.

```yaml
podman_enable_extra_repo: true
podman_extra_repo_url: https://repo.internal.example.com/podman/ubuntu-22.04
podman_extra_repo_key_url: https://repo.internal.example.com/podman/Release.key
```

### Rootless users and subordinate IDs

| Variable | Default | Description |
| --- | --- | --- |
| `podman_rootless_users` | `[]` | Users needing rootless Podman. See the format below. |
| `podman_subid_count` | `65536` | Size of each subordinate ID range. |
| `podman_subid_auto_start` | `200000` | First ID used by the auto-allocator. |
| `podman_system_migrate_on_change` | `true` | Run `podman system migrate` after a range changes. |
| `podman_enable_linger` | `true` | Enable systemd linger so user services start at boot. |

Each `podman_rootless_users` entry is a mapping:

```yaml
podman_rootless_users:
  - name: myapp            # required
    subuid_start: 300000   # optional, auto-allocated when omitted
    count: 65536           # optional, defaults to podman_subid_count
```

### Configuration files

| Variable | Default | Description |
| --- | --- | --- |
| `podman_manage_registries` | `false` | Manage `/etc/containers/registries.conf`. |
| `podman_registries_search` | `[]` | Unqualified search registries, in order. |
| `podman_registries_insecure` | `[]` | Registries reachable over plain HTTP or with an untrusted certificate. |
| `podman_manage_containers_conf` | `false` | Manage the rootless network backend in `containers.conf`. |
| `podman_rootless_network_cmd` | `pasta` | `pasta` or `slirp4netns`. Only applied when the above is `true`. |

## Public interface: `tasks/rootless.yml`

`tasks/rootless.yml` is a supported entry point for other roles, not just an
implementation detail. `podman_app` calls it directly to provision a single
app's subordinate ID range, one call per application, without re-running the
rest of this role:

```yaml
- name: Ensure subordinate ID ranges exist for the service account
  ansible.builtin.include_role:
    name: podman
    tasks_from: rootless.yml
  vars:
    podman_rootless_users:
      - name: "{{ my_app_user }}"
        count: 65536
    podman_enable_linger: true
```

Contract: set `podman_rootless_users` (and optionally `podman_enable_linger`,
`podman_subid_count`, `podman_subid_auto_start`,
`podman_system_migrate_on_change`) and the file provisions exactly those
users. It validates its own input (`assert-rootless-users.yml`) regardless of
whether it's reached through `main.yml` or called directly this way, so
callers get the same fail-fast guarantees either way. Any change to this
contract is a **MAJOR** version bump (see Versioning below).

## Why subuid/subgid are set explicitly

The `user` module assigns subordinate ID ranges **only** when it creates a brand
new account, and only when the distribution's `useradd` defaults enable it. A
pre-existing account — one created by an earlier playbook, a golden image or by
hand — is never touched, and rootless Podman then fails with
`cannot find UID/GID`.

This role therefore reads `/etc/subuid` and `/etc/subgid`, skips users who
already own a range, allocates non-overlapping ranges above the highest existing
one, and applies them with `usermod --add-subuids/--add-subgids`. When a range
changes, `podman system migrate` runs as that user so the new mapping takes
effect on existing storage.

## Usage

```yaml
- hosts: container_hosts
  become: true
  roles:
    - role: podman
      vars:
        podman_version: ""
        podman_rootless_users:
          - name: myapp
```

Tag-scoped runs:

```bash
ansible-playbook site.yml --tags podman-install
ansible-playbook site.yml --tags podman-rootless
ansible-playbook site.yml --check --diff
```

## Verification and troubleshooting

```bash
# Version and Quadlet availability
podman --version
ls /usr/libexec/podman/quadlet

# Rootless readiness for a service account
grep '^myapp:' /etc/subuid /etc/subgid
loginctl show-user myapp --property=Linger

# Rootless smoke test as the service account
sudo -u myapp XDG_RUNTIME_DIR=/run/user/$(id -u myapp) podman info
sudo -u myapp XDG_RUNTIME_DIR=/run/user/$(id -u myapp) podman run --rm docker.io/library/alpine:3 echo ok
```

| Symptom | Cause | Fix |
| --- | --- | --- |
| `cannot find UID/GID` | No subuid/subgid range | Add the user to `podman_rootless_users` and re-run. |
| `Error: cannot re-exec process` | Ranges changed while storage existed | `sudo -u <user> podman system migrate`. |
| User service dies at logout | Linger disabled | `loginctl enable-linger <user>`. |
| `XDG_RUNTIME_DIR not set` | Non-login `become` session | Export `XDG_RUNTIME_DIR=/run/user/$(id -u <user>)`. |

## Versioning

This role follows semantic versioning; see [CHANGELOG.md](CHANGELOG.md).

- **MAJOR** — renaming or restructuring a variable (e.g. `podman_rootless_users`
  changing shape), dropping support for an OS family, raising the minimum
  Ansible or Podman version, changing the subuid allocation strategy in a way
  that would move ranges for existing hosts, or changing the
  `tasks/rootless.yml` public interface (see above) in a way that breaks
  `podman_app` or other callers.
- **MINOR** — adding support for a new distribution, adding a new optional
  variable, or adding a new tagged task block.
- **PATCH** — fixing idempotency or check-mode bugs, correcting package names,
  fixing template or permission errors.
