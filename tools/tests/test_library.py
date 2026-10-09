"""Tests for tools/library.py.

    uv run --with pytest --with pyyaml --with jsonschema pytest tools/tests

Each test builds a small library in a temporary directory: the repository's
real `schema/` directory, plus the items the test writes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import library  # noqa: E402

PERSONA_ID = "0c5b2a3e-8f1d-4e7a-9b3c-2d1e0f9a8b7c"
OTHER_ID = "7d2e4f6a-1b3c-4d5e-8f9a-0b1c2d3e4f5a"
THIRD_ID = "3f1e2d4c-5b6a-4789-8a0b-1c2d3e4f5a6b"


def item(item_id: str = PERSONA_ID, *, title: str = "A persona",
         description: str = "Does one thing well.", extra: str = "",
         body: str = "Be helpful.\n") -> str:
    return (f"---\nid: {item_id}\ntitle: {title}\ndescription: {description}\n{extra}---\n\n"
            f"{body}")


@pytest.fixture
def lib(tmp_path: Path) -> Path:
    shutil.copytree(REPO / "schema", tmp_path / "schema")
    (tmp_path / "personas").mkdir()
    (tmp_path / "prompts").mkdir()
    return tmp_path


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def findings(root: Path, base: str | None = None) -> list[library.Finding]:
    lib = library.Library(root)
    items, found = library.load(lib)
    if base:
        found += library.base_findings(lib, items, base)
    return found


def errors(root: Path, base: str | None = None) -> list[library.Finding]:
    return [f for f in findings(root, base) if f.level == "error"]


# ---------------------------------------------------------------------------
# 3.2 discovery and parsing


def test_valid_item_has_no_findings(lib):
    write(lib, "personas/kent-beck.md", item())
    assert findings(lib) == []


def test_nested_file_is_rejected(lib):
    write(lib, "personas/extra/kent-beck.md", item())
    [error] = errors(lib)
    assert error.path == "personas/extra/kent-beck.md"
    assert "flat" in error.message


@pytest.mark.parametrize("name", ["Kent-Beck", "kent_beck", "-kent", "kent--beck", "a" * 65])
def test_bad_slug_is_rejected(lib, name):
    write(lib, f"personas/{name}.md", item())
    [error] = errors(lib)
    assert "slug" in error.message


def test_non_markdown_file_is_rejected(lib):
    write(lib, "personas/kent-beck.txt", item())
    [error] = errors(lib)
    assert ".md" in error.message


def test_gitkeep_is_ignored(lib):
    write(lib, "personas/.gitkeep", "")
    assert findings(lib) == []


def test_missing_front_matter_is_rejected(lib):
    write(lib, "personas/kent-beck.md", "Be helpful.\n")
    [error] = errors(lib)
    assert "front matter" in error.message and error.line == 1


def test_unclosed_front_matter_is_rejected(lib):
    write(lib, "personas/kent-beck.md", f"---\nid: {PERSONA_ID}\n")
    [error] = errors(lib)
    assert "never closed" in error.message


def test_non_mapping_yaml_is_rejected(lib):
    write(lib, "personas/kent-beck.md", "---\n- a\n- b\n---\n\nBody\n")
    [error] = errors(lib)
    assert "mapping" in error.message


def test_invalid_yaml_is_rejected(lib):
    write(lib, "personas/kent-beck.md", "---\nid: [unclosed\n---\n\nBody\n")
    [error] = errors(lib)
    assert "not valid YAML" in error.message


def test_unsafe_yaml_tag_is_rejected(lib):
    write(lib, "personas/kent-beck.md",
          "---\nid: !!python/object/apply:os.system ['true']\n---\n\nBody\n")
    [error] = errors(lib)
    assert "not valid YAML" in error.message


def test_empty_body_is_rejected(lib):
    write(lib, "personas/kent-beck.md", item(body="  \n\n"))
    [error] = errors(lib)
    assert "no content" in error.message


# ---------------------------------------------------------------------------
# 3.3 schema validation


def test_unknown_field_is_rejected(lib):
    write(lib, "personas/kent-beck.md", item(extra="avatar: x.png\n"))
    [error] = errors(lib)
    assert "`avatar`" in error.message and error.line == 5


def test_missing_required_field_is_rejected(lib):
    write(lib, "personas/kent-beck.md", f"---\nid: {PERSONA_ID}\ntitle: T\n---\n\nBody\n")
    [error] = errors(lib)
    assert error.message == "`description` is required"


def test_multi_line_description_is_rejected(lib):
    write(lib, "personas/kent-beck.md", item(description='"one\\ntwo"'))
    [error] = errors(lib)
    assert error.message == "`description` must be a single line" and error.line == 4


def test_over_long_title_is_rejected(lib):
    write(lib, "personas/kent-beck.md", item(title="x" * 81))
    [error] = errors(lib)
    assert error.message == "`title` is longer than 80 characters" and error.line == 3


@pytest.mark.parametrize("bad_id", ["kent-beck", PERSONA_ID.upper(), '"{' + PERSONA_ID + '}"'])
def test_non_uuid_id_is_rejected(lib, bad_id):
    write(lib, "personas/kent-beck.md", item(bad_id))
    [error] = errors(lib)
    assert error.message.startswith("`id` must be a UUID") and error.line == 2


def test_each_violation_is_its_own_error(lib):
    write(lib, "personas/kent-beck.md",
          item("nope", title="x" * 81, extra="tags: [Bad Tag]\nmood: calm\n"))
    messages = sorted(e.message for e in errors(lib))
    assert len(messages) == 4
    assert any("tags" in m for m in messages)
    assert any("`mood`" in m for m in messages)


def test_tags_must_be_unique_and_few(lib):
    tags = ", ".join(f"t{i}" for i in range(11))
    write(lib, "personas/a.md", item(extra=f"tags: [{tags}]\n"))
    write(lib, "personas/b.md", item(OTHER_ID, extra="tags: [x, x]\n"))
    messages = {e.path: e.message for e in errors(lib)}
    assert "more than 10" in messages["personas/a.md"]
    assert "same entry twice" in messages["personas/b.md"]


# ---------------------------------------------------------------------------
# 3.4 cross-file rules


def test_duplicate_id_names_both_files(lib):
    write(lib, "personas/kent-beck.md", item())
    write(lib, "prompts/review.md", item())
    [error] = errors(lib)
    assert error.path == "prompts/review.md"
    assert "personas/kent-beck.md" in error.message


def test_same_slug_in_different_kinds_is_allowed(lib):
    write(lib, "personas/review.md", item())
    write(lib, "prompts/review.md", item(OTHER_ID))
    assert errors(lib) == []


# Two files that differ only in case are one slug on a case-insensitive file
# system, and the uppercase one already fails the slug rule. The duplicate
# rule is exercised directly instead.
def test_duplicate_slug_within_kind_is_rejected():
    def make(path):
        return library.Item(kind="persona", slug="kent-beck", path=path, raw=b"", body="",
                            front={"id": None}, field_lines={}, body_line=1)
    [error] = library.cross_findings([make("personas/kent-beck.md"),
                                      make("personas/kent-beck.md")])
    assert "slugs must be unique" in error.message


# ---------------------------------------------------------------------------
# 3.5 prompt variables


def prompt_warnings(lib, body):
    write(lib, "prompts/p.md", item(body=body))
    return [f for f in findings(lib) if f.level == "warning"]


@pytest.mark.parametrize("body", [
    "Work in {{folder.name}} on {{branch}} for {{ agent.name }} on {{date}}.\n",
    "Literal \\{{repo}} is escaped.\n",
    "An unclosed {{repo is left alone.\n",
    "No variables at all.\n",
])
def test_prompt_without_unknown_variables_has_no_warning(lib, body):
    assert prompt_warnings(lib, body) == []


def test_unknown_prompt_variable_warns_without_failing(lib):
    [warning] = prompt_warnings(lib, "Line one\n\nOpen {{repo}} now.\n")
    assert "`{{repo}}`" in warning.message
    assert warning.line == 9  # front matter is lines 1-5, a blank line, then the body
    assert errors(lib) == []
    assert library.main(["check"], root=lib) == 0


def test_variable_names_are_case_sensitive(lib):
    [warning] = prompt_warnings(lib, "{{Branch}}\n")
    assert "`{{Branch}}`" in warning.message


def test_personas_are_not_scanned_for_variables(lib):
    write(lib, "personas/p.md", item(body="{{repo}}\n"))
    assert findings(lib) == []


def test_variable_set_matches_knot_app():
    # Knot-App crates/knot-agent-launch/src/variables.rs, PromptVariable::ALL.
    assert library.PROMPT_VARIABLES == {"agent.name", "agent.id", "agent.type", "folder",
                                        "folder.name", "workspace", "branch", "date"}


# ---------------------------------------------------------------------------
# 3.6 identity rules against a base


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def commit_all(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


# The commit that deleted `personas/retired.md` in each `repo` fixture.
DELETING: dict[Path, str] = {}


@pytest.fixture
def repo(lib):
    git(lib, "init", "-q", "-b", "master")
    write(lib, "personas/kent-beck.md", item())
    write(lib, "personas/retired.md", item(OTHER_ID))
    commit_all(lib, "seed")
    (lib / "personas/retired.md").unlink()
    deleting = commit_all(lib, "retire")
    git(lib, "branch", "base")
    git(lib, "checkout", "-q", "-b", "change")
    DELETING[lib] = deleting
    return lib


def test_unchanged_tree_passes_base_check(repo):
    assert errors(repo, "base") == []


def test_new_item_with_fresh_id_passes(repo):
    write(repo, "personas/new.md", item(THIRD_ID))
    commit_all(repo, "add")
    assert errors(repo, "base") == []


def test_changed_id_is_rejected(repo):
    write(repo, "personas/kent-beck.md", item(THIRD_ID))
    commit_all(repo, "change id")
    [error] = errors(repo, "base")
    assert f"changed from {PERSONA_ID}" in error.message and error.line == 2


def test_new_item_reusing_live_id_is_rejected(repo):
    write(repo, "prompts/copy.md", item())
    commit_all(repo, "copy")
    messages = [e.message for e in errors(repo, "base")]
    # Both the in-tree duplicate rule and the base rule apply.
    assert any("already belongs to personas/kent-beck.md on the base branch" in m
               for m in messages)


def test_new_item_reusing_deleted_id_names_deleting_commit(repo):
    write(repo, "personas/revived.md", item(OTHER_ID))
    commit_all(repo, "revive")
    [error] = errors(repo, "base")
    assert DELETING[repo][:12] in error.message and "never reused" in error.message


def test_renamed_item_keeping_its_id_passes(repo):
    git(repo, "mv", "personas/kent-beck.md", "personas/beck.md")
    commit_all(repo, "rename")
    assert errors(repo, "base") == []


def test_renamed_item_changing_its_id_is_rejected(repo):
    git(repo, "mv", "personas/kent-beck.md", "personas/beck.md")
    write(repo, "personas/beck.md", item(THIRD_ID))
    commit_all(repo, "rename and change")
    [error] = errors(repo, "base")
    assert f"changed from {PERSONA_ID}" in error.message


def test_check_command_exits_nonzero_on_base_error(repo, capsys):
    write(repo, "personas/kent-beck.md", item(THIRD_ID))
    commit_all(repo, "change id")
    assert library.main(["check", "--base", "base"], root=repo) == 1


# ---------------------------------------------------------------------------
# 3.7 output formats


def snapshot_tree(lib):
    write(lib, "personas/kent-beck.md", item("nope"))
    write(lib, "prompts/p.md", item(OTHER_ID, body="100% {{repo}}\n"))


def test_human_output_snapshot(lib, capsys):
    snapshot_tree(lib)
    assert library.main(["check"], root=lib) == 1
    assert capsys.readouterr().out == (
        "error: personas/kent-beck.md:2: `id` must be a UUID in lowercase hyphenated form, "
        "like 0c5b2a3e-8f1d-4e7a-9b3c-2d1e0f9a8b7c\n"
        "warning: prompts/p.md:7: `{{repo}}` is not a Knot prompt variable and will be sent as "
        "written; known variables are {{agent.id}}, {{agent.name}}, {{agent.type}}, {{branch}}, "
        "{{date}}, {{folder}}, {{folder.name}}, {{workspace}} (write `\\{{` for a literal `{{`)\n"
        "2 items checked: 1 errors, 1 warnings\n")


def test_github_output_snapshot(lib, capsys):
    snapshot_tree(lib)
    assert library.main(["check", "--format", "github"], root=lib) == 1
    assert capsys.readouterr().out == (
        "::error file=personas/kent-beck.md,line=2::`id` must be a UUID in lowercase hyphenated "
        "form, like 0c5b2a3e-8f1d-4e7a-9b3c-2d1e0f9a8b7c\n"
        "::warning file=prompts/p.md,line=7::`{{repo}}` is not a Knot prompt variable and will "
        "be sent as written; known variables are {{agent.id}}, {{agent.name}}, {{agent.type}}, "
        "{{branch}}, {{date}}, {{folder}}, {{folder.name}}, {{workspace}} (write `\\{{` for a "
        "literal `{{`)\n")


def test_github_output_escapes_workflow_command_characters():
    finding = library.Finding("error", "a.md", "50%\nnext\r")
    assert finding.github() == "::error file=a.md::50%25%0Anext%0D"


# ---------------------------------------------------------------------------
# 4.x index


@pytest.fixture
def indexed(repo):
    write(repo, "prompts/review.md",
          item(THIRD_ID, title="Revisión", description="Ünïcode stays as written.",
               extra="tags: [review]\nauthors: [Ada]\n", body="On {{branch}}.\n"))
    commit_all(repo, "content")
    return repo


def generate(root: Path, capsys) -> dict:
    assert library.main(["index", "--dry-run"], root=root) == 0
    return json.loads(capsys.readouterr().out)


def test_index_validates_against_its_schema(indexed, capsys):
    document = generate(indexed, capsys)
    schema = json.loads((REPO / "schema/index.schema.json").read_text())
    Draft202012Validator(schema).validate(document)
    assert document["commit"] == git(indexed, "rev-parse", "HEAD")
    assert document["kinds"] == {"persona": {"directory": "personas", "count": 1},
                                 "prompt": {"directory": "prompts", "count": 1}}
    assert [i["path"] for i in document["items"]] == ["personas/kent-beck.md",
                                                      "prompts/review.md"]
    review = document["items"][1]
    assert review["tags"] == ["review"] and review["authors"] == ["Ada"]
    assert document["items"][0]["tags"] == [] and document["items"][0]["authors"] == []


def test_index_order_is_kind_then_slug(lib, capsys):
    write(lib, "prompts/a.md", item(THIRD_ID))
    write(lib, "personas/z.md", item(OTHER_ID))
    write(lib, "personas/b.md", item())
    git(lib, "init", "-q")
    commit_all(lib, "x")
    assert [i["path"] for i in generate(lib, capsys)["items"]] == [
        "personas/b.md", "personas/z.md", "prompts/a.md"]


# 4.3: the hash covers the exact bytes a client downloads. A client fetches
# `raw.githubusercontent.com/<repo>/<commit>/<path>`, which serves the blob
# at that commit, so hashing `git show <commit>:<path>` checks the same
# bytes. The live curl check against GitHub is end-to-end task 7.1.
def test_index_hash_matches_committed_blob(indexed, capsys):
    document = generate(indexed, capsys)
    for entry in document["items"]:
        blob = subprocess.run(["git", "show", f"{document['commit']}:{entry['path']}"],
                              cwd=indexed, check=True, capture_output=True).stdout
        assert entry["size"] == len(blob)
        assert entry["sha256"] == hashlib.sha256(blob).hexdigest()


def test_index_text_is_deterministic(indexed, capsys):
    library.main(["index"], root=indexed)
    first = (indexed / "index.json").read_bytes()
    library.main(["index"], root=indexed)
    second = (indexed / "index.json").read_bytes()
    strip = lambda b: b.split(b'"kinds"', 1)[1]  # noqa: E731 - drop the timestamp header
    assert strip(first) == strip(second)
    assert first.endswith(b"}\n") and b"\r" not in first
    assert "Revisión".encode() in first  # ensure_ascii=False
    text = first.decode()
    assert text == json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n"
    assert list(json.loads(text)) == ["format", "commit", "generatedAt", "kinds", "items"]


def test_changed_reports_only_real_changes(indexed):
    assert library.main(["index", "--changed"], root=indexed) == 0  # no index yet
    library.main(["index"], root=indexed)
    assert library.main(["index", "--changed"], root=indexed) == 1
    write(indexed, "personas/kent-beck.md", item(description="Now different."))
    assert library.main(["index", "--changed"], root=indexed) == 0


def test_changed_ignores_commit_and_timestamp(indexed):
    library.main(["index"], root=indexed)
    commit_all(indexed, "index")  # HEAD moves, content does not
    assert library.main(["index", "--changed"], root=indexed) == 1


def test_dry_run_does_not_write(indexed, capsys):
    library.main(["index", "--dry-run"], root=indexed)
    assert not (indexed / "index.json").exists()


def test_index_refuses_invalid_content(lib, capsys):
    write(lib, "personas/kent-beck.md", item("nope"))
    assert library.main(["index", "--dry-run"], root=lib) == 2
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# The repository's own content


def test_repository_content_is_clean():
    assert findings(REPO) == []


def test_seed_personas_keep_knot_app_ids():
    expected = {f"a1000001-0000-0000-0000-00000000000{n}" for n in range(1, 8)}
    lib = library.Library(REPO)
    items, _ = library.load(lib)
    assert {i.front["id"] for i in items if i.kind == "persona"} == expected
