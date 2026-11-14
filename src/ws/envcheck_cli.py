"""`ws env check`: the env var names a repo reads, against the Parameter Store and argocd.

Exit codes: 0 nothing to fix, 1 a name is missing or still set in argocd, 2 setup (config,
credentials, commit not found), 3 the Parameter Store could not be listed.
"""

import argparse
import json
import sys

from ws import envcheck
from ws.userconfig import ConfigInvalid, ConfigMissing

EXIT_FINDINGS = 1
EXIT_SETUP = 2
EXIT_STORE = 3


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "env",
        help="Env var names a repo reads against the Parameter Store.",
        description=(
            "Names only: no value of the Parameter Store is ever read, printed or kept. "
            "Configured in the [env_check] table of config.toml."
        ),
    )
    commands = parser.add_subparsers(dest="env_command", required=True)
    check = commands.add_parser(
        "check",
        help="Compare the names the code reads with the Parameter Store and the argocd values.",
        description=(
            "Reads the code at a commit (never the working tree), lists the Parameter Store "
            "names under the environment's prefix and reads the argocd values. Exit 0 when no "
            "required name is missing and no name is left in argocd, 1 otherwise, 2 for a setup "
            "problem, 3 when the store cannot be listed."
        ),
    )
    check.add_argument("repo", help="a key of [env_check.repos]")
    check.add_argument("--env", required=True, help="an environment of the repo's prefix table")
    code = check.add_mutually_exclusive_group(required=True)
    code.add_argument("--ref", help="branch, release branch or sha to check (must exist locally)")
    code.add_argument(
        "--deployed",
        action="store_true",
        help="the commit of the image tag in the environment's argocd values",
    )
    check.add_argument(
        "--strict",
        action="store_true",
        help="a name with a default missing from the store also fails (for a release); "
        "same as strict = true in [env_check] or in the repo's table",
    )
    check.add_argument("--json", action="store_true", help="print JSON instead of PT-BR text")
    check.set_defaults(handler=_cmd_check)


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        result = _check(args)
    except (ConfigMissing, ConfigInvalid, envcheck.SetupError) as error:
        print(f"ws env check: {error}", file=sys.stderr)
        return EXIT_SETUP
    except envcheck.StoreUnreachable as error:
        print(f"ws env check: {error}", file=sys.stderr)
        return EXIT_STORE
    print(
        json.dumps(result, ensure_ascii=False, indent=2)
        if args.json
        else envcheck.render_text(result)
    )
    return 0 if result["ok"] else EXIT_FINDINGS


def _check(args: argparse.Namespace) -> dict:
    settings = envcheck.load_settings()
    profile = settings.repos.get(args.repo)
    if profile is None:
        known = ", ".join(sorted(settings.repos)) or "none"
        raise envcheck.SetupError(f"{args.repo} is not in [env_check.repos] (configured: {known})")
    if args.env not in profile.prefix:
        configured = ", ".join(sorted(profile.prefix))
        raise envcheck.SetupError(
            f"{args.repo} has no prefix.{args.env} (configured: {configured})"
        )
    ref = None if args.deployed else args.ref
    target = ref or envcheck.deployed_sha(profile.argocd, profile.values.get(args.env, []))
    sha = envcheck.resolve_commit(profile.path, target)

    only = (
        (lambda path: path.endswith(".py"))
        if profile.kind == "python"
        else (lambda path: path in profile.shell_files)
    )
    files = envcheck.files_at(profile.path, sha, only=only)
    if profile.kind == "python":
        scan = envcheck.scan_python(files, profile)
    else:
        scan = envcheck.scan_shell(files, list(profile.shell_files))
    argocd_names, warnings = _argocd(profile, args.env)
    store = envcheck.store_names(settings, profile, args.env)
    if not store:
        warning = (
            f"the Parameter Store returned 0 names under prefix.{args.env} of "
            f"[env_check.repos.{args.repo}]: check the prefix (or the script's output format)"
        )
        print(f"ws env check: warning: {warning}", file=sys.stderr)
        warnings.insert(0, warning)
    repo_strict = profile.strict if profile.strict is not None else settings.strict

    compared = envcheck.compare(
        scan,
        store,
        argocd_names,
        list(settings.role_vars),
        list(profile.always_required),
        ignore=profile.ignore,
        strict=args.strict or repo_strict,
    )
    return {
        "repo": args.repo,
        "env": args.env,
        "source": settings.source,
        "commit": {"ref": ref, "sha": sha, "deployed": args.deployed},
        **compared,
        "warnings": [*scan.warnings, *warnings],
    }


def _argocd(profile: envcheck.RepoProfile, env: str) -> tuple[set[str], list[str]]:
    names: set[str] = set()
    warnings: list[str] = []
    files = profile.values.get(env, [])
    if not files:
        warnings.append(f"[env_check.repos.{profile.name}] has no values.{env}; argocd not checked")
    for name in files:
        try:
            text = (profile.argocd / name).read_text(encoding="utf-8")
        except OSError:
            warnings.append(f"{name}: values file not found; argocd not checked")
            continue
        found, problems = envcheck.argocd_env_names(name, text)
        names |= found
        warnings.extend(problems)
    return names, warnings
