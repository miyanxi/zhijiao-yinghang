import re


def matched_names(message: str, names: list[str]) -> list[str]:
    spans = []
    for name in names:
        spans.extend((match.start(), match.end(), name) for match in re.finditer(re.escape(name), message))
    chosen = []
    for start, end, name in sorted(spans, key=lambda item: (-(item[1] - item[0]), item[0])):
        if not any(start < other_end and end > other_start for other_start, other_end, _ in chosen):
            chosen.append((start, end, name))
    return [name for _, _, name in sorted(chosen)]
