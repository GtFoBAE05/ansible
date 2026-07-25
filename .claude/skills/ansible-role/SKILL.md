---
name: ansible-role
description: Builds production-ready, OS-agnostic Ansible roles following a research-first workflow — verify upstream docs before writing tasks, then apply a fixed structure (defaults vs vars, first_found OS loading, orchestrator tasks/main.yml, assert-based validation, Molecule + tests, README, CHANGELOG) and validate with ansible-lint. Checks against common role anti-patterns (god role, hidden cross-role coupling, dead handlers, missing Molecule tests). Use when asked to create, scaffold, refactor, or review an Ansible role, or to package existing playbook logic into a role.
---

# Production-Ready Ansible Roles

Roles built without checking current upstream docs encode stale practice.
**Research before writing tasks.** Deprecations are the usual trap: a tool that
was correct two years ago may now be deprecated in favour of a replacement.

## Step 0 — Research first (do not skip)

Before writing any task, verify against **official documentation, not blog
posts**:

1. **Is the mechanism still current?** Search for deprecation notices on every
   core command or module the role will use. Quote the notice verbatim if found.
2. **Minimum versions.** What version introduced the feature you rely on? Which
   target distros ship something older?
3. **Defaults that changed.** Backends, drivers and network stacks change
   defaults between major versions. Never assume — check.
4. **Behaviour on pre-existing state.** Many Ansible modules only apply settings
   when *creating* a resource, and silently skip resources that already exist.
   Verify the module actually does what you assume for existing hosts.

**State the findings explicitly before implementing.** If a finding contradicts
the request, say so before writing code.

### Distro version reality check

Build a table before choosing a minimum version. A target that ships something
too old needs an explicit decision — extra repo, hard failure, or dropped
support. Do not paper over it.

| OS | Ships | Meets minimum? |
|---|---|---|
| … | … | ✅ / ❌ needs extra repo |

Never wire in a third-party repo without checking it is still maintained. Dead
repos are common; prefer a generic, user-supplied repo variable (default off)
over hardcoding one.

## Structure

```
roles/<name>/
├── defaults/main.yml          # user-overridable, LOW precedence
├── vars/
│   ├── main.yml               # internal constants, HIGH precedence
│   ├── Debian.yml             # OS-family values
│   ├── RedHat.yml
│   └── default.yml            # fallback
├── tasks/
│   ├── main.yml               # orchestrator ONLY — imports/includes
│   ├── assert.yml             # fail fast on bad input
│   ├── install-Debian.yml     # OS-specific
│   ├── install-RedHat.yml
│   ├── install-default.yml
│   └── configure.yml          # shared logic
├── handlers/main.yml
├── templates/*.j2
├── meta/main.yml
├── molecule/default/       # primary automated test — see Testing below
│   ├── molecule.yml
│   ├── converge.yml
│   ├── verify.yml
│   └── prepare.yml         # only if pre-existing state must be seeded
├── tests/{inventory,test.yml}  # lightweight manual/CI smoke check, not a Molecule substitute
├── README.md
└── CHANGELOG.md
```

### defaults vs vars — do not mix

- `defaults/main.yml` — the role's public API. Everything a user may reasonably
  override. Lowest precedence.
- `vars/main.yml` — internal constants (paths, unit names, regexes, enum lists
  used by asserts). Users should not touch these. High precedence.

If you find yourself telling a user "override this var", it belongs in
`defaults/`.

### OS-agnostic loading — no scattered `when:`

Concentrate OS detection at load time. Do **not** sprinkle
`when: ansible_os_family == 'Debian'` across tasks.

```yaml
- name: Load OS family specific variables
  ansible.builtin.include_vars: "{{ lookup('ansible.builtin.first_found', _params) }}"
  vars:
    _params:
      files:
        - "{{ ansible_distribution }}-{{ ansible_distribution_major_version }}.yml"
        - "{{ ansible_distribution }}.yml"
        - "{{ ansible_os_family }}.yml"
        - default.yml
      paths:
        - "{{ role_path }}/vars"

- name: Install packages
  ansible.builtin.include_tasks: "{{ lookup('ansible.builtin.first_found', _install) }}"
  vars:
    _install:
      files:
        - "install-{{ ansible_os_family }}.yml"
        - install-default.yml
      paths:
        - "{{ role_path }}/tasks"
```

Always include a `default.yml` fallback so an unlisted distro fails on a real
package name, not on a missing-file error.

Use the generic `package` module in shared paths; drop to `apt`/`dnf` only for
genuinely package-manager-specific behaviour (cache updates, repo config).

### tasks/main.yml is an orchestrator

Imports and includes only — no long inline task lists.

```yaml
- name: Validate role parameters
  ansible.builtin.import_tasks: assert.yml
  tags: [always, <role>, <role>-validate]

- name: Install
  ansible.builtin.include_tasks: "..."
  tags: [<role>, <role>-install]

- name: Configure
  ansible.builtin.import_tasks: configure.yml
  tags: [<role>, <role>-config]
```

Tag granularly so `--tags <role>-install` works.

## Fail fast with assert

Validate at the top, before any change. Every `fail_msg` states what was wrong,
what is expected, and what was received.

```yaml
- name: Assert the application name is valid
  ansible.builtin.assert:
    that:
      - app_name is string
      - app_name | length > 0
      - app_name is match('^[a-z0-9][a-z0-9_-]*$')
    fail_msg: >-
      'app_name' is required and must be lowercase alphanumeric with hyphens
      or underscores. It becomes the systemd unit name.
      Got: '{{ app_name | default('') }}'.
```

Validate enums against lists in `vars/main.yml`. Catch *contradictory*
combinations too, not just malformed values — e.g. an auto-update policy that
can never fire because the image is pinned by digest.

## Idempotency and check mode

- Prefer modules over `command`/`shell`. When a command is unavoidable, use
  `creates:`/`removes:` **inside the module args**, not at task level — `removes`
  as a task-level key is a fatal "conflicting action statements" error.
- Set `changed_when: false` for read-only commands.
- Guard anything that cannot run in dry-run with `when: not ansible_check_mode`.
- Handlers use variable-based names, never hardcoded strings, and are check-mode
  safe.
- Registering a fact from a skipped task yields undefined — always `| default()`.
- **`omit` only works as a direct module-parameter value.** Nested inside a
  dict/list literal you build yourself (e.g. an item in a `vars:` block passed
  to `include_role`), `{{ x | default(omit, true) }}` does **not** remove the
  key — it leaves the literal string `__omit_place_holder__<hash>` as the
  value, which then silently passes every `is defined`/type check and corrupts
  anything downstream that does math on it (e.g. `| int` on a placeholder
  string silently returns `0`). If you need a key conditionally absent from a
  hand-built structure, either build it with `| combine({'k': v} if cond else
  {})`, or just pass the raw (possibly empty/falsy) value through and make the
  consumer treat falsy the same as absent — e.g. `item.k | default(fallback,
  true)`, where the trailing `true` already covers both undefined *and* falsy.
  Verify this by actually running the task (Molecule/converge), not by
  reading it — the placeholder string looks correct in a `--check` diff.

## Handlers — no dead code

Every handler must be reachable from at least one `notify:` in the role.
Before finishing, grep for each handler name across `tasks/`:

```bash
grep -n "notify" roles/<name>/tasks/*.yml
```

A handler nobody notifies is not "prepared for later" — it is untested dead
code that will drift silently. Delete it, or wire the `notify:` that was
missing. Restart/reload via handler, never `state: restarted` inline in
`tasks/main.yml` — that always reports changed and always restarts, even on a
no-op run.

## Dependencies and multi-instance roles

`meta/main.yml`:

```yaml
dependencies:
  - role: <bootstrap_role>

# Only when the role must apply more than once per play:
allow_duplicates: true
```

**Trap:** `allow_duplicates: true` plus a `meta` dependency re-runs the
dependency for every instance. Guard the dependency with a fact so later passes
are no-ops:

```yaml
- name: Check whether bootstrap already ran
  ansible.builtin.set_fact:
    _bootstrap_pending: "{{ not (bootstrap_completed | default(false)) }}"

# ... every block gets: when: _bootstrap_pending

- name: Mark bootstrap complete
  ansible.builtin.set_fact:
    bootstrap_completed: true
```

Galaxy `platforms` is schema-validated. EL 9/10 is `name: EL` + `versions: [all]`
— numeric versions there fail ansible-lint.

### Cross-role reuse — no hidden coupling

A dependency role sometimes exposes more than `meta.dependencies` covers — e.g.
a per-instance role calling a specific task file of its bootstrap dependency
directly, with `include_role: {name: <dep>, tasks_from: <file>.yml}`, once per
instance, instead of the whole role. This is a **cross-role anti-pattern**
unless made explicit:

1. **Treat the called file as a public interface, not an implementation
   detail.** Document its variable contract (what it reads, what it does) in
   the dependency role's README, under a heading like
   `## Public interface: tasks/<file>.yml`.
2. **Make that file self-validating.** `tasks_from:` bypasses the dependency's
   own `tasks/main.yml`, so it also bypasses `tasks/assert.yml`. If the file
   depends on validated input, factor that specific validation into its own
   task file (e.g. `assert-<thing>.yml`) and `import_tasks` it both from
   `assert.yml` (for the normal path) and from the reused file itself (for the
   direct-call path) — never rely on the caller having gone through the
   dependency's own entry point.
3. **Never reach into another role's internal variables** (`vars/main.yml`,
   `set_fact` results) from outside it. Pass everything explicitly through the
   documented `vars:` on the `include_role` call.
4. Note in the dependency's Versioning section that changing this file's
   contract is a **MAJOR** bump, same as any other public variable.

## Privilege model

When the connection user is an unprivileged sudo account, use two layers:

- `become: true` — root, for account/directory/system provisioning.
- `become_user: <service account>` — for anything scoped to that user.

For user-scoped systemd, `become` creates no login session, so set the runtime
dir explicitly on every such task:

```yaml
become: true
become_user: "{{ app_user }}"
environment:
  XDG_RUNTIME_DIR: "/run/user/{{ app_uid }}"
```

Resolve the UID with `getent`, not by assuming.

## Documentation

**README.md** — every overridable variable in tables grouped by concern, a usage
example, a multi-instance example when relevant, a manual
verification/troubleshooting section with real commands, and a symptom→cause→fix
table.

**CHANGELOG.md** — starts at `1.0.0`, Keep a Changelog format. In the README,
state what triggers a bump **for this specific role**:

- **MAJOR** — renaming/retyping a variable, changing a file layout or naming
  scheme that orphans existing deployments, dropping an OS family.
- **MINOR** — new optional variables, new distro support, new tagged blocks.
- **PATCH** — idempotency/check-mode fixes, package name corrections, template
  and permission fixes.

## Destructive operations

An `absent` state should stop services and remove managed config, but **not**
silently delete user data or accounts. Leave data in place and document the
manual removal command. Deleting data as a side effect of a state flag is
surprising and unrecoverable.

## Testing with Molecule

`tests/test.yml` alone ("run it once against localhost/an inventory and eyeball
it") is the anti-pattern the article calls out — it catches nothing across OS
versions and nothing on repeated runs. Molecule is the default automated test
for every role that manages installable state (packages, services, files);
skip it only for pure orchestrator/meta roles with no tasks of their own, and
say so explicitly.

Scenario shape (`roles/<name>/molecule/default/`):

```yaml
# molecule.yml
dependency:
  name: galaxy
  options:
    requirements-file: ../../../../requirements.yml   # repo-root requirements, if present
driver:
  name: docker
platforms:
  - name: <name>-ubuntu2404
    image: "geerlingguy/docker-ubuntu2404-ansible:latest"
    pre_build_image: true
    privileged: true            # only if the role needs it (systemd, nested containers, cgroups)
    override_command: false     # REQUIRED if privileged/systemd — see note below
    cgroupns_mode: host
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
    groups: [<name>_hosts]
  - name: <name>-rockylinux9   # a second OS family is the point — catches vars/<Family>.yml bugs
    image: "geerlingguy/docker-rockylinux9-ansible:latest"
    pre_build_image: true
    privileged: true
    override_command: false
    cgroupns_mode: host
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
    groups: [<name>_hosts]
provisioner:
  name: ansible
  env:
    ANSIBLE_ROLES_PATH: "${MOLECULE_PROJECT_DIRECTORY}/.."   # so meta dependencies resolve
scenario:
  test_sequence: [dependency, create, prepare, converge, idempotence, verify, destroy]
```

Notes:

- The `geerlingguy/docker-<distro>-ansible` images ship a working systemd
  entrypoint — use them for any role that manages services, not a bare distro
  image plus a hand-rolled `command: /sbin/init`.
- **`override_command: false` is required whenever you rely on that systemd
  entrypoint.** The molecule docker driver's default (`override_command: true`)
  replaces the image's own `CMD` with its own keep-alive command, so PID 1
  becomes a plain `bash`/`sleep` process instead of `systemd` — every
  `systemctl`/`loginctl`/`--user` call then fails with "System has not been
  booted with systemd as init system", which reads exactly like a real bug in
  the role. Confirm PID 1 directly if this ever comes up:
  `docker exec <container> ps -p 1 -o comm`.
- `privileged: true` + the cgroup mount is only needed when the role itself
  drives systemd units, nested containers, or namespaces inside the test
  container. A plain config-file role doesn't need it — don't cargo-cult it in.
- `idempotence` in `test_sequence` is what actually enforces the "Breaking
  Idempotence" anti-pattern: converge runs twice, second run must report zero
  changes.
- `verify.yml` should assert real outcomes (`ansible.builtin.assert` on facts
  gathered with `slurp`/`stat`/`command` + `changed_when: false`), not just
  "the playbook didn't fail."
- Keep `tests/test.yml` as a lighter-weight manual/CI smoke playbook — it is
  useful for a quick check against a real host — but it does not replace
  Molecule for automated, multi-OS, idempotence-checked coverage.

Run it from inside the role directory:

```bash
cd roles/<name> && molecule test
```

If Docker/Podman is unavailable in the environment, say so explicitly rather
than skipping Molecule silently — report it as "not runnable here" in the
final report, not as "tested."

## Validation before finishing

Run these and report real output — never claim a role is validated without
having run something.

```bash
ansible-playbook --syntax-check -i roles/<name>/tests/inventory roles/<name>/tests/test.yml
ansible-lint roles/<name>
yamllint roles/<name>          # optional; ansible-lint already runs yamllint
cd roles/<name> && molecule test   # primary — see Testing with Molecule above
```

Target `Passed: 0 failure(s), 0 warning(s) ... profile 'production'`.

**On Windows control nodes:** `ansible-core` cannot run — it requires `grp`,
`pwd` and `multiprocessing` fork. Do not fake it with module shims; that tests
the shims. Use WSL (`wsl.exe -d <distro> -- bash <script>`) for genuine
validation. In Git Bash, prefix with `MSYS_NO_PATHCONV=1` or `/mnt/...` paths get
mangled into Windows paths.

Custom filter plugins go in `filter_plugins/` and should be unit-tested directly
with `python3` — cheaper than a full playbook run, and it catches parsing bugs.

Clean up scratch validation scripts afterwards, and gitignore `__pycache__/` and
`.ansible/`.

## Honest final report

Close by separating, explicitly:

- **Production-ready as-is** — what was validated and how.
- **Must adapt to your environment** — internal repos, registry auth, ID ranges
  already in use, firewall, SELinux labels, anything left as a stub.
- **Not tested at runtime** — say plainly when validation was static only
  (syntax/lint) because no target host existed. Recommend `--check --diff`
  against staging first.

Never present lint-clean as equivalent to working.
