"""Auto-update de la propia app (no bloqueante)."""
from __future__ import annotations


def parse_semver(s: str) -> tuple[int, int, int]:
    parts = str(s).split(".")
    nums = [int(p) for p in (parts + ["0", "0", "0"])[:3]]
    return (nums[0], nums[1], nums[2])


def is_newer(remote: str, local: str) -> bool:
    try:
        return parse_semver(remote) > parse_semver(local)
    except (ValueError, TypeError):
        return False


def check_for_update(local_version: str, app_version_fn) -> dict | None:
    try:
        info = app_version_fn()
    except Exception:
        return None
    remote = info.get("version") if isinstance(info, dict) else None
    if remote and is_newer(remote, local_version):
        return info
    return None
