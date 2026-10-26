"""Common-word dictionaries of the new-word check: the Debian `wamerican` and `wbrazilian` lists.

A capitalized word at the start of a sentence is probably an ordinary word, so the check lets the
dictionaries clear it there (see `ws.newwords`). The files are looked up in the ws data dir first,
then in `/usr/share/dict/`; `install` puts them in the data dir without root.

Every function reads or installs; the callers decide what a missing dictionary means.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ws import config
from ws.names import fold

SUBPROCESS_TIMEOUT = 300
DATA_SUBDIR = "dict"
PACKAGE_DICT_PATH = Path("usr/share/dict")
MANUAL_COMMAND = "sudo apt-get install wamerican wbrazilian"


@dataclass(frozen=True)
class Source:
    package: str
    filename: str


SOURCES = (Source("wamerican", "american-english"), Source("wbrazilian", "brazilian"))


class InstallError(Exception):
    """The dictionaries could not be downloaded or put in place."""


def data_path() -> Path:
    return config.data_dir() / DATA_SUBDIR


def find(source: Source) -> Path | None:
    """The file of a dictionary: the data dir wins over the system one."""
    for folder in (data_path(), config.system_dict_dir()):
        path = folder / source.filename
        if path.is_file():
            return path
    return None


def missing() -> list[Source]:
    return [source for source in SOURCES if find(source) is None]


def load() -> frozenset[str]:
    """The folded entries of the dictionaries found; empty when there is none.

    Only entries that start with a lowercase letter and hold letters alone count: a capitalized
    entry is a proper noun (a first name) and an apostrophe or hyphen never matches a word.
    """
    words: set[str] = set()
    for source in SOURCES:
        path = find(source)
        if path is None:
            continue
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                entry = line.strip()
                if entry[:1].islower() and entry.isalpha():
                    words.add(fold(entry))
    return frozenset(words)


def _run(command: list[str], cwd: Path) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError(f"{Path(command[0]).name} {command[1]} failed: {error}") from error
    if result.returncode != 0:
        lines = [line for line in (result.stderr or result.stdout).splitlines() if line.strip()]
        detail = lines[-1].strip() if lines else f"exit {result.returncode}"
        raise InstallError(f"{Path(command[0]).name} {command[1]} failed: {detail}")


def _deb_of(downloads: Path, package: str) -> Path:
    found = sorted(downloads.glob(f"{package}_*.deb"))
    if len(found) != 1:
        raise InstallError(f"apt-get download did not leave exactly one {package} package")
    return found[0]


def _checked(staged: Path, unpacked: Path) -> Path:
    """The dictionary of an unpacked package, refused unless it is a real, non-empty file in it."""
    inside = staged.resolve().is_relative_to(unpacked.resolve())
    if staged.is_symlink() or not inside or not staged.is_file() or staged.stat().st_size == 0:
        raise InstallError(f"{staged.name} is missing or empty in its package")
    return staged


def _put_in_place(staged: Path, target: Path) -> None:
    partial = target.with_name(f".{target.name}.partial")
    try:
        shutil.copyfile(staged, partial)
        os.replace(partial, target)
    except OSError as error:
        raise InstallError(f"could not write {target}: {error}") from error
    finally:
        partial.unlink(missing_ok=True)


def install() -> list[Path]:
    """Download both packages without root and copy their dictionaries into the data dir.

    `apt-get download` checks each package against the signed apt index; `dpkg -x` only unpacks
    it. The work happens in a throwaway folder of the cache dir, removed at the end.
    """
    apt_get = shutil.which("apt-get")
    dpkg = shutil.which("dpkg")
    if apt_get is None or dpkg is None:
        raise InstallError("apt-get or dpkg was not found")
    try:
        config.cache_dir().mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="dict-", dir=config.cache_dir()))
    except OSError as error:
        raise InstallError(
            f"could not create a work folder in {config.cache_dir()}: {error}"
        ) from error
    try:
        downloads = work / "downloads"
        downloads.mkdir()
        _run([apt_get, "download", *(source.package for source in SOURCES)], downloads)
        staged: dict[str, Path] = {}
        for source in SOURCES:
            folder = work / f"unpacked-{source.package}"
            folder.mkdir()
            _run([dpkg, "-x", str(_deb_of(downloads, source.package)), str(folder)], work)
            staged[source.filename] = _checked(folder / PACKAGE_DICT_PATH / source.filename, folder)
        target = data_path()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise InstallError(f"could not create {target}: {error}") from error
        for filename, path in staged.items():
            _put_in_place(path, target / filename)
        return [target / filename for filename in staged]
    finally:
        shutil.rmtree(work, ignore_errors=True)
