"""CLI entry point for cooklint: lint Cooklang recipe files for app-breaking mistakes.

Pure-stdlib regex-based linter. No parser dependency, so it is stable across
cooklang-py versions and works on the ``>>`` header style this repo uses.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --- Checks that catch the real app bugs this repo hit -----------------------

# Timer: `~name{value%unit}` or `~{value%unit}` (name may contain spaces and
# non-ASCII letters such as æ/ø/å).
TIMER_RE = re.compile(r"~([\w ]*)\{(.*?)\}")

# Units the Cooklang mobile app can turn into a real count. Anything else
# (Danish "minutter"/"timer", or "min") resolves to a 0-minute timer.
CANONICAL_UNITS = {
    "minute", "minutes", "hour", "hours", "second", "seconds",
}

# Cooklang splits directions into steps at BLANK lines. Two consecutive
# non-blank method lines collapse into a single step in the app.
STEP_SEP_RE = re.compile(r"~~[^\n]*\n{2}[^\n]*", re.MULTILINE)

_SERVICE_FRONTMATTER_START = re.compile(r"^\s*---\s*$")


def _timer_unit(value: str) -> str:
    """Unit portion of a timer value after the last ``%`` ('' if none)."""
    if "%" not in value:
        return ""
    return value.split("%")[-1].strip().lower()


def _timer_range(value: str) -> bool:
    """True if the timer quantity is a range (e.g. ``15 - 18`` or ``10-15``)."""
    return "-" in value.split("%")[0]


def lint_file(path: Path) -> list[tuple[str, int, str]]:
    """Return (severity, line, message) findings for one recipe file."""
    findings: list[tuple[str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [("error", 0, f"cannot read: {exc}")]

    # Skip YAML frontmatter so the step-collapse check only reads method lines.
    body = text
    lines = text.split("\n")
    if len(lines) >= 2 and _SERVICE_FRONTMATTER_START.match(lines[0].strip()):
        end = 1
        while end < len(lines) and not _SERVICE_FRONTMATTER_START.match(lines[end].strip()):
            end += 1
        if end < len(lines):
            body = "\n".join(lines[end + 1 :])

    # 1-3) Timers: unit present, canonical unit, and single (non-range) value.
    for m in TIMER_RE.finditer(body):
        value = m.group(2)
        char_pos = m.start()
        line = text.count("\n", 0, char_pos) + 1

        if "%" not in value:
            findings.append(
                ("error", line,
                 f"timer '~{m.group(1) or ''}{{{value}}}' has no unit; app shows 0 "
                 "(use e.g. '~{{20%minutes}}')")
            )
            continue

        if _timer_range(value):
            findings.append(
                ("error", line,
                 f"timer value '{value.split('%')[0]}' is a range; the app can't time a "
                 "range, pick one nominal value")
            )

        unit = _timer_unit(value)
        if unit not in CANONICAL_UNITS:
            findings.append(
                ("error", line,
                 f"timer unit '{unit!r}' is not canonical ({', '.join(sorted(CANONICAL_UNITS))}); "
                 "the app resolves these to 0")
            )

    # 4) Step collapse: consecutive method lines with no blank line between.
    for m in STEP_SEP_RE.finditer(body):
        char_pos = m.start()
        line = text.count("\n", 0, char_pos) + 1
        findings.append(
            ("warning", line,
             "no blank line between consecutive direction lines; the app merges "
             "them into a single step")
        )

    # 5) Scaling: a servings declaration must exist for the app to scale amounts.
    if not re.search(r"^\s*(>>\s*)?servings\s*[:=]\s*\S", text, re.MULTILINE):
        findings.append(
            ("warning", 0,
             "no 'servings:' declaration; the app cannot scale ingredient amounts")
        )

    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cooklint", description=__doc__)
    ap.add_argument("paths", nargs="*", help="recipe files or directories")
    ap.add_argument("--quiet", action="store_true", help="skip the end summary")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for p in (args.paths or ["."]):
        pth = Path(p)
        if pth.is_dir():
            files.extend(pth.rglob("*.cook"))
        elif pth.is_file() and pth.suffix == ".cook":
            files.append(pth)
        else:
            print(f"skipping non-.cook path: {pth}", file=sys.stderr)
    if not files:
        print("no .cook files matched", file=sys.stderr)
        return 2

    all_findings: list[tuple[str, Path, int, str]] = []
    for f in sorted(set(files)):
        for sev, line, msg in lint_file(f):
            all_findings.append((sev, f, line, msg))

    for sev, f, line, msg in all_findings:
        loc = f"{f}" if line == 0 else f"{f}:{line}"
        print(f"{sev.upper():7} {loc}: {msg}")

    errors = sum(1 for x in all_findings if x[0] == "error")
    warnings = sum(1 for x in all_findings if x[0] == "warning")
    if not args.quiet:
        print(f"\n{len(files)} files, {errors} errors, {warnings} warnings")
    return 1 if errors or warnings else 0


if __name__ == "__main__":
    sys.exit(main())
