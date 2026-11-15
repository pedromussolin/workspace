"""Pastas 700 e arquivos 600 sob a pasta de dados: o que carrega consulta da empresa."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from ws.config import data_dir

PRIVATE_FOLDER = 0o700


def private_folder(folder: Path) -> None:
    """Folders 700 from `projects` down to `folder`."""
    top = data_dir() / "projects"
    top.parent.mkdir(parents=True, exist_ok=True)
    chain = [top]
    for part in folder.relative_to(top).parts:
        chain.append(chain[-1] / part)
    for each in chain:
        each.mkdir(mode=PRIVATE_FOLDER, exist_ok=True)
        each.chmod(PRIVATE_FOLDER)


@contextmanager
def private_file(target: Path) -> Iterator[BinaryIO]:
    """A 600 temp file beside `target`, moved over it by `os.replace` when the block ends well."""
    handle, temporary = tempfile.mkstemp(
        prefix=f".{target.name}-", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            yield stream
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
