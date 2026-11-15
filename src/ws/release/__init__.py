"""`ws release`: build, publish, move and report the release of the company repos."""

import json
import sys
from collections.abc import Callable

EXIT_RULE, EXIT_SETUP, EXIT_CONFLICT = 1, 2, 3


class ReleaseSetup(Exception):
    """A precondition is missing (config, gh, gate settings, a merge in progress): exit 2."""


class ReleaseRefused(Exception):
    """A rule failed and nothing was written: exit 1. `payload` is printed as JSON when given."""

    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload


def run(name: str, action: Callable[[], tuple[dict, int]]) -> int:
    """Runs a command and prints its JSON. A `gh` or `git` that cannot answer while the command
    reads is exit 2, the same as any missing precondition; imported here so `ws.release` stays
    light for the CLI."""
    from ws.release.github import GhFailed, GhUncertain
    from ws.release.gitops import GitFailed

    try:
        payload, code = action()
    except ReleaseSetup as error:
        print(f"ws release {name}: {error}", file=sys.stderr)
        return EXIT_SETUP
    except (GhFailed, GhUncertain) as error:
        print(f"ws release {name}: gh: {error}", file=sys.stderr)
        return EXIT_SETUP
    except GitFailed as error:
        print(f"ws release {name}: git: {error}", file=sys.stderr)
        return EXIT_SETUP
    except ReleaseRefused as error:
        if error.payload is not None:
            print(json.dumps(error.payload, ensure_ascii=False, indent=2))
        print(f"ws release {name}: {error}", file=sys.stderr)
        return EXIT_RULE
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code
