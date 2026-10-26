"""`ws names review`: answer the pending new words one by one in the terminal.

A real name goes to `names.toml` with an analog; a harmless word goes to `.known-words`. History
is never rewritten here: after real names are added the loop only reports what carries them, and
the `pre-push` range check keeps blocking those commits until they are rewritten.
"""

from pathlib import Path

from ws import names, newwords, secrets
from ws.config import config_dir
from ws.names import Name, NamesTable

ANSWERS = {"r": "real", "h": "harmless", "s": "skip", "": "skip", "q": "quit"}


def _ask(prompt: str) -> str | None:
    """One line of input; None when the input ended."""
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def _answer(item: newwords.NewWord) -> str:
    print(f"{item.word}: {newwords.format_places(item)}")
    while True:
        reply = _ask("  [r]eal name, [h]armless, [s]kip, [q]uit? ")
        if reply is None:
            return "quit"
        if reply.lower() in ANSWERS:
            return ANSWERS[reply.lower()]
        print("  answer r, h, s or q")


def _add_real(item: newwords.NewWord, added: list[Name]) -> bool:
    analog = _ask("  analog: ")
    if not analog:
        print("  no analog given: skipped")
        return False
    try:
        names.add_name(config_dir() / "names.toml", item.word, analog)
    except ValueError as error:
        print(f"  refused: {error}")
        return False
    added.append(Name(item.word, analog))
    print("  added to names.toml")
    return True


def _carriers(repo: Path, table: NamesTable, revs: list[str]) -> None:
    """Where the new real names are, in the work tree and in the unpushed commits."""
    print("Work-tree files that carry them (mask each with `ws mask --in-place FILE`):")
    paths = secrets._git(repo, "ls-files", "-z").decode("utf-8", errors="replace").split("\0")
    in_tree = []
    for path in filter(None, paths):
        text = secrets._decode((repo / path).read_bytes()) if (repo / path).is_file() else None
        if text is not None:
            in_tree.extend(
                f"  {found.path}:{found.line}"
                for found in secrets.scan_text(path, text, table, [])
                if found.rule == "real-name"
            )
    print("\n".join(in_tree) or "  none")
    print("Unpushed commits that carry them (the push stays blocked until they are rewritten):")
    in_commits = [
        f"  {found.commit[:10]} {found.path}:{found.line}"
        for found in secrets.check_range(repo, revs, table)
        if found.rule == "real-name"
    ]
    print("\n".join(in_commits) or "  none")


def run_review(repo: Path, pending: list[newwords.NewWord], revs: list[str]) -> int:
    if not pending:
        print("no pending new words")
        return 0
    added: list[Name] = []
    harmless: list[str] = []
    skipped = 0
    for position, item in enumerate(pending, start=1):
        print(f"[{position}/{len(pending)}] ", end="")
        answer = _answer(item)
        if answer == "quit":
            skipped += len(pending) - position + 1
            break
        if answer == "real" and _add_real(item, added):
            continue
        if answer == "harmless":
            newwords.add_known_words(repo, [item.word])
            harmless.append(item.word)
            continue
        skipped += 1  # also a real name that was refused or had no analog
    print(f"{len(added)} real name(s), {len(harmless)} harmless word(s), {skipped} skipped.")
    if harmless:
        print(f"Commit {newwords.KNOWN_WORDS_FILE}: the push reads it from the commit.")
    if added:
        _carriers(repo, NamesTable(tuple(added), ()), revs)
    return 0
