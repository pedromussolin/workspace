"""Review signals from the changes of a card: migrations and env vars. Pure but `new_side`."""

import stat
from pathlib import Path

from ws.envcheck import (
    DEFAULT_EXCLUDE_GLOBS,
    CodeName,
    EnvCheckSettings,
    RepoProfile,
    scan_python,
    scan_shell,
)
from ws.release.migrations import MigrationUnreadable, Revision, heads, parse_revision


def _parsed(
    sources: dict[str, str], warnings: list[str], warn_for: set[str] | None = None
) -> dict[str, Revision]:
    out: dict[str, Revision] = {}
    for path, source in sorted(sources.items()):
        try:
            parsed = parse_revision(source, path)
        except MigrationUnreadable as exc:
            if warn_for is None or path in warn_for:
                warnings.append(str(exc))
            continue
        if parsed is not None:
            out[parsed.revision] = parsed
    return out


def migration_report(
    base: dict[str, str], new: dict[str, str]
) -> tuple[dict, list[str], list[str]]:
    warnings: list[str] = []
    changed = sorted(p for p in base if p in new and base[p] != new[p])
    before = _parsed(base, [], set())
    touched = {p for p in new if p not in base} | set(changed)
    after = _parsed(new, warnings, touched)
    flags: list[str] = []
    deleted = sorted(p for p in base if p not in new)
    flags.extend(f"existing migration changed: {p}" for p in changed)
    flags.extend(f"existing migration deleted: {p}" for p in deleted)
    added = [
        {"path": r.path, "revision": r.revision, "down_revision": list(r.down)}
        for r in sorted(after.values(), key=lambda r: r.path)
        if r.path not in base and r.revision not in before
    ]
    heads_after = heads(after)
    if len(heads_after) > 1:
        flags.append(f"more than one Alembic head after the change: {', '.join(heads_after)}")
    report = {
        "added": added,
        "changed_existing": changed,
        "heads_before": heads(before),
        "heads_after": heads_after,
    }
    return report, flags, warnings


def _scan(files: dict[str, bytes], profile: RepoProfile) -> tuple[dict[str, CodeName], list[str]]:
    result = scan_python(files, profile)
    names = dict(result.names)
    warnings = list(result.warnings)
    if profile.shell_files:
        shell = scan_shell(files, list(profile.shell_files))
        for name, item in shell.names.items():
            names.setdefault(name, item)
        warnings.extend(shell.warnings)
    return names, warnings


def env_report(
    base: dict[str, bytes], new: dict[str, bytes], profile: RepoProfile, changed: set[str]
) -> tuple[dict, list[str], list[str]]:
    before, _ = _scan(base, profile)
    after, scan_warnings = _scan(new, profile)
    added = [
        {"name": n, "required": after[n].required, "where": list(after[n].where)}
        for n in sorted(after)
        if n not in before or (after[n].required and not before[n].required)
    ]
    removed = sorted(n for n in before if n not in after)
    prefixes = tuple(f"{path}:" for path in changed)
    flags = [
        f"required env var added: {e['name']}; check the Parameter Store"
        for e in added
        if e["required"]
    ]
    warnings = [w for w in scan_warnings if w.startswith(prefixes)]
    return {"added": added, "removed": removed}, flags, warnings


def profile_for(name: str, path: Path, settings: EnvCheckSettings | None) -> RepoProfile:
    if settings is not None and name in settings.repos:
        return settings.repos[name]
    return RepoProfile(
        name=name,
        path=path,
        argocd=path,
        kind="python",
        prefix={},
        values={},
        profile={},
        helpers=(),
        migration_globs=(),
        always_required=(),
        shell_files=(),
        dynamic={},
        exclude_globs=DEFAULT_EXCLUDE_GLOBS,
    )


def new_side(
    base: dict[str, bytes], root: Path, removed: list[str], present: list[str]
) -> dict[str, bytes]:
    gone = set(removed)
    out = {p: c for p, c in base.items() if p not in gone}
    real_root = root.resolve()
    for rel in present:
        if ".." in Path(rel).parts:
            continue
        file = root / rel
        try:
            if not file.parent.resolve().is_relative_to(real_root):
                continue
            if not stat.S_ISREG(file.lstat().st_mode):
                continue
            out[rel] = file.read_bytes()
        except OSError:
            continue
    return out
