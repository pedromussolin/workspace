"""Dev ids: how the shared repo names a person without a name, an analog or an e-mail."""

import hashlib
import re

DEV_ID = re.compile(r"dev-[0-9a-f]{10}")


def dev_id(email: str) -> str:
    """`dev-` and the first 10 hex characters of the SHA-256 of the trimmed, lowercased e-mail."""
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    return f"dev-{digest[:10]}"
