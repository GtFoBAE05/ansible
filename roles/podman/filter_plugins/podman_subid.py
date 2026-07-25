"""Filter plugins for parsing /etc/subuid and /etc/subgid content."""

from __future__ import annotations


def podman_parse_subid(content):
    """Parse subuid/subgid file content into a list of range entries.

    Each non-comment line has the form ``name:start:count``. Returns a list of
    dicts with ``name``, ``start``, ``count`` and ``next_free`` keys, where
    ``next_free`` is the first ID after the entry's range. Malformed and
    non-numeric lines are ignored so a hand-edited file cannot break the run.
    """
    entries = []

    for line in (content or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split(":")
        if len(parts) != 3:
            continue

        name, start, count = (part.strip() for part in parts)
        if not name:
            continue

        try:
            start_id = int(start)
            count_id = int(count)
        except ValueError:
            continue

        entries.append(
            {
                "name": name,
                "start": start_id,
                "count": count_id,
                "next_free": start_id + count_id,
            }
        )

    return entries


class FilterModule(object):
    def filters(self):
        return {"podman_parse_subid": podman_parse_subid}
