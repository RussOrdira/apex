from __future__ import annotations

import re

BANNED_TOKENS = {"hate", "slur", "abuse"}


def is_name_allowed(name: str) -> bool:
    lowered = name.lower()
    for token in BANNED_TOKENS:
        if token in lowered:
            return False
    return bool(re.match(r"^[a-zA-Z0-9 _\-]{3,120}$", name))
