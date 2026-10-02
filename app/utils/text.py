"""Title casing and light text cleanup. Acronyms and tokens like Cas9 stay intact."""

from __future__ import annotations

import html
import re

SMALL_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "but",
    "or",
    "nor",
    "for",
    "in",
    "of",
    "on",
    "at",
    "to",
    "from",
    "by",
    "with",
    "as",
    "into",
    "over",
    "via",
    "vs",
}


def collapse(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def strip_tags(value: str | None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return collapse(text)


def looks_like_acronym_token(token: str) -> bool:
    core = token.strip("()[]{}.,;:\"'`")
    if not core:
        return False
    if re.search(r"[A-Za-z]\d|\d[A-Za-z]", core):
        return True
    letters = re.sub(r"[^A-Za-z]", "", core)
    if len(letters) >= 2 and letters.isupper():
        return True
    if re.search(r"[A-Z].*[A-Z]", core) and not core.isupper():
        return True
    return False


def _is_shouting(title: str) -> bool:
    letters = [char for char in title if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def cap_first_alpha(text: str) -> str:
    chars = list(text)
    for index, char in enumerate(chars):
        if char.isalpha():
            chars[index] = char.upper()
            break
    return "".join(chars)


def _sentence_word(word: str, shout: bool) -> str:
    parts = word.split("-")
    changed = []
    for part in parts:
        if not shout and looks_like_acronym_token(part):
            changed.append(part)
        else:
            changed.append(part.lower())
    return "-".join(changed)


def sentence_case(title: str | None) -> str:
    collapsed = collapse(title)
    if not collapsed:
        return ""
    shout = _is_shouting(collapsed)
    words = [_sentence_word(word, shout) for word in collapsed.split(" ")]
    text = " ".join(words)
    text = cap_first_alpha(text)
    return re.sub(r"([:.?!]\s+)([a-z])", lambda match: match.group(1) + match.group(2).upper(), text)


def _title_piece(piece: str, shout: bool, force_cap: bool) -> str:
    if piece == "":
        return piece
    if not shout and looks_like_acronym_token(piece):
        return piece
    lower = piece.lower()
    bare = re.sub(r"[^a-z0-9]", "", lower)
    if not force_cap and bare in SMALL_WORDS:
        return lower
    return cap_first_alpha(lower)


def title_case(title: str | None) -> str:
    collapsed = collapse(title)
    if not collapsed:
        return ""
    shout = _is_shouting(collapsed)
    words = collapsed.split(" ")
    result: list[str] = []
    for index, word in enumerate(words):
        pieces = re.split(r"(-)", word)
        built: list[str] = []
        word_pieces = [piece for piece in pieces if piece != "-"]
        piece_index = 0
        for piece in pieces:
            if piece == "-":
                built.append(piece)
                continue
            force = index == 0 or index == len(words) - 1 or piece_index == 0
            # Small words stay small in the middle of a hyphenated word except the first piece.
            if piece_index > 0 and index not in (0, len(words) - 1):
                force = False
            built.append(_title_piece(piece, shout, force_cap=force or (index == 0 and piece_index == 0)))
            piece_index += 1
        result.append("".join(built))
    # Second pass: uncapitalize small words that are not first or last.
    fixed: list[str] = []
    for index, word in enumerate(result):
        bare = re.sub(r"[^A-Za-z]", "", word).lower()
        if 0 < index < len(result) - 1 and bare in SMALL_WORDS and not looks_like_acronym_token(word):
            fixed.append(word.lower())
        else:
            fixed.append(word)
    return " ".join(fixed)


def normalize_match(value: str | None) -> str:
    text = collapse(value).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return collapse(text)


def first_title_word(title: str | None) -> str:
    for word in re.findall(r"[A-Za-z0-9]+", title or ""):
        if word.lower() not in {"a", "an", "the", "of", "on", "in", "and", "for", "with", "from"}:
            cleaned = word[:24]
            return cleaned[0].upper() + cleaned[1:]
    return "Ref"
