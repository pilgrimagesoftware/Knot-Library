# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6",
#     "jsonschema>=4.18",
# ]
# ///
"""Validate Knot-Library content and generate its index.

    uv run tools/library.py check [--base <ref>] [--format human|github]
    uv run tools/library.py index [--dry-run | --changed] [--output index.json]

`check` validates every item against the content format (openspec spec
`content-format`). With `--base`, it also applies the identity rules against
that ref: an existing item's id never changes, and a new item never reuses an
id the base has or once had. `index` generates `index.json` (spec
`content-index`).

Both run from the repository root, which is found from this file's location,
so the same command works locally and in CI.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent

INDEX_FORMAT = 1
INDEX_FILE = "index.json"
REGISTRY_FILE = "schema/kinds.json"

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MAX = 64

# Knot's prompt variables (Knot-App `knot-agent-launch` `PromptVariable`).
# A `{{name}}` outside this set is still a valid prompt - Knot leaves it as
# written - but it is almost always a typo, so it warns.
PROMPT_VARIABLES = frozenset({
    "agent.name",
    "agent.id",
    "agent.type",
    "folder",
    "folder.name",
    "workspace",
    "branch",
    "date",
})
OPEN, CLOSE, ESCAPE = "{{", "}}", "\\"

# Files a kind directory may hold that are not items.
IGNORED_FILES = frozenset({".gitkeep"})


@dataclasses.dataclass(frozen=True)
class Finding:
    """One error or warning about one file."""

    level: str  # "error" or "warning"
    path: str  # repository-relative, `/`-separated
    message: str
    line: int | None = None

    def human(self) -> str:
        where = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{self.level}: {where}: {self.message}"

    def github(self) -> str:
        location = f"file={self.path}" + ("" if self.line is None else f",line={self.line}")
        # `%`, CR and LF must be escaped in workflow command data.
        message = self.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return f"::{self.level} {location}::{message}"


@dataclasses.dataclass
class Item:
    """One parsed library item."""

    kind: str
    slug: str
    path: str  # repository-relative
    raw: bytes
    front: dict
    body: str
    field_lines: dict  # front matter field -> line number in the file
    body_line: int  # line number where the body starts


class Library:
    """The repository's kind registry and schemas, rooted at `root`."""

    def __init__(self, root: Path):
        self.root = root
        self.kinds: dict = json.loads((root / REGISTRY_FILE).read_text(encoding="utf-8"))
        resources = []
        for schema_path in sorted((root / "schema").glob("*.schema.json")):
            contents = json.loads(schema_path.read_text(encoding="utf-8"))
            resources.append((contents["$id"], Resource.from_contents(contents)))
        self.registry = Registry().with_resources(resources)
        self.validators = {}
        for kind, entry in self.kinds.items():
            schema = json.loads((root / entry["schema"]).read_text(encoding="utf-8"))
            self.validators[kind] = Draft202012Validator(schema, registry=self.registry)


# ---------------------------------------------------------------------------
# Discovery and parsing


def discover(library: Library) -> tuple[list[tuple[str, Path]], list[Finding]]:
    """Every item file, as `(kind, path)` in kind then slug order, plus the
    findings about files that cannot be items: nested files, non-Markdown
    files and bad slugs."""
    found: list[tuple[str, Path]] = []
    findings: list[Finding] = []
    for kind in sorted(library.kinds):
        directory = library.root / library.kinds[kind]["directory"]
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_dir() or path.name in IGNORED_FILES:
                continue
            rel = relative(library.root, path)
            if path.parent != directory:
                findings.append(Finding("error", rel,
                                        f"items must sit directly in `{directory.name}/`: "
                                        "kind directories are flat"))
                continue
            if path.suffix != ".md":
                findings.append(Finding("error", rel, "items must be Markdown files ending in `.md`"))
                continue
            slug = path.stem
            if not SLUG.match(slug) or len(slug) > SLUG_MAX:
                findings.append(Finding("error", rel,
                                        f"`{slug}` is not a valid slug: use 1 to {SLUG_MAX} "
                                        "lowercase letters, digits and single hyphens, "
                                        "starting and ending with a letter or digit"))
                continue
            found.append((kind, path))
    return found, findings


def parse(library: Library, kind: str, path: Path) -> tuple[Item | None, list[Finding]]:
    """Reads one item: front matter as a YAML mapping, and a non-empty body."""
    rel = relative(library.root, path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        return None, [Finding("error", rel, f"the file is not valid UTF-8 ({error.reason})")]
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None, [Finding("error", rel, "the file must begin with front matter: a `---` line", 1)]
    closing = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r") == "---"), None)
    if closing is None:
        return None, [Finding("error", rel, "the front matter is never closed with a `---` line", 1)]
    front_text = "\n".join(lines[1:closing])
    try:
        front = yaml.safe_load(front_text)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = None if mark is None else mark.line + 2
        return None, [Finding("error", rel, f"the front matter is not valid YAML: {error}", line)]
    if not isinstance(front, dict):
        return None, [Finding("error", rel, "the front matter must be a YAML mapping of fields", 2)]
    body = "\n".join(lines[closing + 1:])
    if not body.strip():
        return None, [Finding("error", rel, "the item has no content after its front matter", closing + 2)]
    field_lines = {}
    for number, line in enumerate(lines[1:closing], start=2):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:", line)
        if match and match.group(1) not in field_lines:
            field_lines[match.group(1)] = number
    return Item(kind=kind, slug=path.stem, path=rel, raw=raw, front=front, body=body,
                field_lines=field_lines, body_line=closing + 2), []


# ---------------------------------------------------------------------------
# Validation


def schema_findings(library: Library, item: Item) -> list[Finding]:
    """One finding per schema violation, naming the field and the rule."""
    findings = []
    validator = library.validators[item.kind]
    for error in sorted(validator.iter_errors(item.front), key=lambda e: list(e.path)):
        field = str(error.path[0]) if error.path else None
        message = describe(error, field)
        line = item.field_lines.get(field) if field else None
        if field is None:
            # Unknown or missing fields: point at the named field when there is one.
            for name in re.findall(r"'([^']+)'", error.message):
                if name in item.field_lines:
                    line = item.field_lines[name]
                    break
        findings.append(Finding("error", item.path, message, line or 2))
    return findings


def describe(error, field: str | None) -> str:
    """A rule written for a contributor rather than in jsonschema's words."""
    rule = error.validator
    value = error.validator_value
    if rule == "required":
        missing = re.findall(r"'([^']+)'", error.message)
        return f"`{missing[0]}` is required" if missing else error.message
    if rule in ("unevaluatedProperties", "additionalProperties"):
        names = re.findall(r"'([^']+)'", error.message)
        fields = ", ".join(f"`{name}`" for name in names) or "a field"
        return f"unknown field {fields}: this kind does not define it"
    where = f"`{field}`" if field else "the front matter"
    if field and error.path and len(error.path) > 1:
        where = f"`{field}` entry {error.path[1] + 1}"
    if rule == "maxLength":
        return f"{where} is longer than {value} characters"
    if rule == "minLength":
        return f"{where} must not be empty"
    if rule == "maxItems":
        return f"{where} has more than {value} entries"
    if rule == "uniqueItems":
        return f"{where} lists the same entry twice"
    if rule == "type":
        return f"{where} must be a {value}"
    if rule == "pattern":
        if field == "id":
            return "`id` must be a UUID in lowercase hyphenated form, like 0c5b2a3e-8f1d-4e7a-9b3c-2d1e0f9a8b7c"
        if field == "tags":
            return f"{where} must be 1 to 32 lowercase letters, digits and hyphens"
        return f"{where} must be a single line"
    return f"{where}: {error.message}"


def prompt_variable_findings(item: Item) -> list[Finding]:
    """Warns on `{{name}}` references Knot does not expand, scanning as
    Knot does: `\\{{` is an escape, the name is trimmed, and an unclosed
    `{{` ends the scan."""
    findings = []
    text = item.body
    offset = 0
    while True:
        open_at = text.find(OPEN, offset)
        if open_at == -1:
            break
        inner_at = open_at + len(OPEN)
        if open_at > 0 and text[open_at - 1] == ESCAPE:
            offset = inner_at
            continue
        close_at = text.find(CLOSE, inner_at)
        if close_at == -1:
            break
        name = text[inner_at:close_at].strip()
        if name not in PROMPT_VARIABLES:
            line = item.body_line + text.count("\n", 0, open_at)
            known = ", ".join(f"{{{{{variable}}}}}" for variable in sorted(PROMPT_VARIABLES))
            findings.append(Finding("warning", item.path,
                                    f"`{{{{{name}}}}}` is not a Knot prompt variable and will be "
                                    f"sent as written; known variables are {known} "
                                    "(write `\\{{` for a literal `{{`)", line))
        offset = close_at + len(CLOSE)
    return findings


def cross_findings(items: list[Item]) -> list[Finding]:
    """Ids unique across the library; slugs unique within a kind."""
    findings = []
    by_id: dict[str, Item] = {}
    for item in items:
        item_id = item.front.get("id")
        if not isinstance(item_id, str):
            continue
        if item_id in by_id:
            first = by_id[item_id]
            findings.append(Finding("error", item.path,
                                    f"`id` {item_id} is also used by {first.path}: ids must be "
                                    "unique across the library", item.field_lines.get("id")))
        else:
            by_id[item_id] = item
    by_slug: dict[tuple[str, str], Item] = {}
    for item in items:
        key = (item.kind, item.slug.lower())
        if key in by_slug:
            findings.append(Finding("error", item.path,
                                    f"slug `{item.slug}` is also used by {by_slug[key].path}: "
                                    "slugs must be unique within a kind"))
        else:
            by_slug[key] = item
    return findings


def load(library: Library) -> tuple[list[Item], list[Finding]]:
    """Every item that parses, and every finding about the tree - except the
    base-branch identity rules, which need a ref."""
    files, findings = discover(library)
    items = []
    for kind, path in files:
        item, problems = parse(library, kind, path)
        findings.extend(problems)
        if item is None:
            continue
        problems = schema_findings(library, item)
        findings.extend(problems)
        if item.kind == "prompt":
            findings.extend(prompt_variable_findings(item))
        items.append(item)
    findings.extend(cross_findings(items))
    return items, findings


# ---------------------------------------------------------------------------
# Identity rules against a base ref


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout


def git_or_none(root: Path, *args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def front_id(text: str | None) -> str | None:
    """An item's `id`, read leniently from a historical file."""
    if text is None:
        return None
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None
    closing = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r") == "---"), None)
    if closing is None:
        return None
    try:
        front = yaml.safe_load("\n".join(lines[1:closing]))
    except yaml.YAMLError:
        return None
    item_id = front.get("id") if isinstance(front, dict) else None
    return item_id if isinstance(item_id, str) else None


def base_findings(library: Library, items: list[Item], base: str) -> list[Finding]:
    """Ids are permanent: an existing item keeps its id, and a new item never
    takes an id the base has or once had."""
    root = library.root
    directories = [entry["directory"] for entry in library.kinds.values()]
    base_paths = [path for path in git(root, "ls-tree", "-r", "--name-only", base, "--",
                                       *directories).splitlines() if path.endswith(".md")]
    base_ids = {path: front_id(git_or_none(root, "show", f"{base}:{path}")) for path in base_paths}
    live_ids = {item_id: path for path, item_id in base_ids.items() if item_id}

    # Renames between the base and the working tree, so a moved item is
    # compared with where it came from.
    renamed_from = {}
    for line in git(root, "diff", "-M", "--name-status", base, "--", *directories).splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("R") and len(parts) == 3:
            renamed_from[parts[2]] = parts[1]

    # Ids of items deleted anywhere in the base's history, with the commit
    # that deleted each.
    retired: dict[str, str] = {}
    log = git(root, "log", "--diff-filter=D", "--name-only", "--format=commit %H", base, "--",
              *directories)
    commit = None
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line.split(" ", 1)[1]
        elif line.strip() and commit:
            item_id = front_id(git_or_none(root, "show", f"{commit}^:{line.strip()}"))
            if item_id and item_id not in live_ids and item_id not in retired:
                retired[item_id] = commit

    findings = []
    for item in items:
        item_id = item.front.get("id")
        if not isinstance(item_id, str):
            continue
        line = item.field_lines.get("id")
        origin = renamed_from.get(item.path, item.path)
        if origin in base_ids:
            was = base_ids[origin]
            if was and was != item_id:
                findings.append(Finding("error", item.path,
                                        f"`id` changed from {was}: ids are permanent once merged",
                                        line))
            continue
        # A new item (or one whose rename git did not detect).
        if item_id in retired:
            findings.append(Finding("error", item.path,
                                    f"`id` {item_id} belonged to an item deleted in commit "
                                    f"{retired[item_id][:12]}: a deleted item's id is never reused",
                                    line))
        elif item_id in live_ids and (root / live_ids[item_id]).exists() \
                and live_ids[item_id] != item.path:
            findings.append(Finding("error", item.path,
                                    f"`id` {item_id} already belongs to {live_ids[item_id]} "
                                    "on the base branch", line))
    return findings


# ---------------------------------------------------------------------------
# Index


def index_entries(library: Library, items: list[Item]) -> tuple[dict, list]:
    """The index's `kinds` and `items`, in their fixed order."""
    kinds = {}
    for kind in sorted(library.kinds):
        kinds[kind] = {
            "directory": library.kinds[kind]["directory"],
            "count": sum(1 for item in items if item.kind == kind),
        }
    entries = []
    for item in sorted(items, key=lambda i: (i.kind, i.slug)):
        entries.append({
            "kind": item.kind,
            "id": item.front["id"],
            "slug": item.slug,
            "title": item.front["title"],
            "description": item.front["description"],
            "tags": list(item.front.get("tags") or []),
            "authors": list(item.front.get("authors") or []),
            "path": item.path,
            "size": len(item.raw),
            "sha256": hashlib.sha256(item.raw).hexdigest(),
        })
    return kinds, entries


def render_index(commit: str, generated_at: str, kinds: dict, entries: list) -> str:
    document = {
        "format": INDEX_FORMAT,
        "commit": commit,
        "generatedAt": generated_at,
        "kinds": kinds,
        "items": entries,
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Commands


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def report(findings: list[Finding], output_format: str, stream) -> None:
    for finding in sorted(findings, key=lambda f: (f.path, f.line or 0, f.level, f.message)):
        print(finding.github() if output_format == "github" else finding.human(), file=stream)


def command_check(args, library: Library) -> int:
    items, findings = load(library)
    if args.base:
        findings.extend(base_findings(library, items, args.base))
    report(findings, args.format, sys.stdout)
    errors = sum(1 for f in findings if f.level == "error")
    warnings = len(findings) - errors
    if args.format == "human":
        print(f"{len(items)} items checked: {errors} errors, {warnings} warnings")
    return 1 if errors else 0


def command_index(args, library: Library) -> int:
    items, findings = load(library)
    errors = [f for f in findings if f.level == "error"]
    if errors:
        report(errors, "human", sys.stderr)
        print("the index cannot be generated until these errors are fixed", file=sys.stderr)
        return 2
    kinds, entries = index_entries(library, items)
    output = library.root / args.output
    if args.changed:
        # Exit 0 when `items` or `kinds` differ from the committed index, so a
        # shell `if` reads naturally; 1 when there is nothing to commit.
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return 0
        same = existing.get("items") == entries and existing.get("kinds") == kinds
        return 1 if same else 0
    commit = git(library.root, "rev-parse", "HEAD").strip()
    text = render_index(commit, now_rfc3339(), kinds, entries)
    if args.dry_run:
        sys.stdout.write(text)
        return 0
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="library.py", description=__doc__.split("\n\n")[0])
    commands = root.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="validate every item against the content format")
    check.add_argument("--base", metavar="REF",
                       help="also apply the identity rules against REF, e.g. origin/master")
    check.add_argument("--format", choices=("human", "github"), default="human",
                       help="`github` prints workflow annotations")

    index = commands.add_parser("index", help="generate index.json")
    mode = index.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the index instead of writing it")
    mode.add_argument("--changed", action="store_true",
                      help="exit 0 if items or kinds differ from the existing index, 1 if not")
    index.add_argument("--output", default=INDEX_FILE, help="where to write the index")
    return root


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = parser().parse_args(argv)
    library = Library(root)
    if args.command == "check":
        return command_check(args, library)
    return command_index(args, library)


if __name__ == "__main__":
    sys.exit(main())
