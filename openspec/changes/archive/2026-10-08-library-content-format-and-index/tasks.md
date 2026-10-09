# Tasks

## 1. Repository basics

- [x] 1.1 Add a CC BY 4.0 `LICENSE` and a `README.md` describing the library, its kinds and the raw index URL, unless the split-repositories change has already landed them; verify `gh repo view pilgrimagesoftware/Knot-Library --json licenseInfo` reports `CC-BY-4.0` after merge
- [x] 1.2 Create the empty kind directories `personas/` and `prompts/` (each with a `.gitkeep` until seeded) and `tools/`; verify `git ls-files` lists them
  - The directories are seeded in this same change, so the final tree never needs the `.gitkeep` placeholders (see 6.3).

## 2. Schemas and kind registry

- [x] 2.1 Write `schema/envelope.schema.json` (draft 2020-12) for the shared front matter: `id` as a lowercase UUID, `title` 1-80 characters on one line, `description` 1-200 characters on one line, optional `tags` (max 10, unique, `^[a-z0-9-]{1,32}$`), optional `authors`, and `additionalProperties: false`; verify it with `uv run --with check-jsonschema check-jsonschema --check-metaschema schema/envelope.schema.json`
- [x] 2.2 Write `schema/persona.schema.json` and `schema/prompt.schema.json`, each composing the envelope and adding no fields; verify both pass the metaschema check
- [x] 2.3 Write `schema/kinds.json`, mapping `persona` → `personas/` and `prompt` → `prompts/` with their schema paths, plus `schema/kinds.schema.json` for the registry itself; verify the registry validates against its schema
- [x] 2.4 Write `schema/index.schema.json` for `index.json` as specified in `content-index` (format, commit, generatedAt, kinds, items, and every item field); verify a hand-written two-item sample validates and a sample missing `sha256` does not

## 3. Validation tool (`tools/library.py check`)

- [x] 3.1 Create `tools/library.py` with PEP 723 inline dependencies (`pyyaml`, `jsonschema`) and `check` and `index` subcommands; verify `uv run tools/library.py --help` lists both
- [x] 3.2 Implement item discovery and parsing: kind directories come from `schema/kinds.json`, files must be flat `.md` with slug-valid names, front matter is read with the safe loader and must be a mapping, and the trimmed body must not be empty; verify with fixture tests under `tools/tests/` covering a nested file, a bad slug, missing front matter, non-mapping YAML and an empty body
- [x] 3.3 Validate front matter against the item's kind schema and report one error per violation with file, field and rule; verify with fixtures for an unknown field, a multi-line description, an over-long title and a non-UUID id
- [x] 3.4 Enforce cross-file rules: unique `id` across all kinds (naming both files) and unique slug within a kind; verify with duplicate-id and duplicate-slug fixtures
- [x] 3.5 Warn on prompt `{{name}}` references outside Knot's variable set, honouring the `\{{` escape; verify a known variable gives no warning, `{{repo}}` warns without failing, and `\{{repo}}` gives no warning
- [x] 3.6 Implement `--base <ref>`: fail when an existing item's `id` changed, or when a new item reuses an id that is live in the base or belongs to an item deleted anywhere in the base's history, naming the deleting commit; verify with a scripted temporary git repo fixture
- [x] 3.7 Add `--format github` output that emits `::error file=...,line=...::` and `::warning ...` annotations, alongside the default human-readable output; verify both formats against a fixture snapshot
- [x] 3.8 Document the local command (`uv run tools/library.py check --base origin/<default-branch>`) and the front matter rules in `CONTRIBUTING.md`; verify the command runs as written in a fresh clone

## 4. Index generator (`tools/library.py index`)

- [x] 4.1 Generate `index.json`: `format: 1`, `commit` from `git rev-parse HEAD`, `generatedAt` in RFC 3339 UTC, `kinds` with directory and count, and items ordered by kind then slug with tags, authors, path, size and SHA-256 of the exact file bytes; verify that the output validates against `schema/index.schema.json`
- [x] 4.2 Make the output deterministic (fixed key order, two-space indent, trailing newline, LF line endings, `ensure_ascii=False`), and add `--dry-run` (print without writing) and `--changed` (exit 0 when `items` and `kinds` differ from the existing `index.json`, 1 when they don't); verify that generating twice gives byte-identical `items` and `kinds`, and that `--changed` reports no change on a rerun
- [x] 4.3 Verify `sha256` against `curl` of a raw URL by hashing a test file fetched at a pinned commit, and record the check in `tools/tests/`
  - Verified locally: `test_index_hash_matches_committed_blob` hashes `git show <commit>:<path>`, the same blob the raw URL serves at a pinned commit. The live `curl` check moves to 7.1.

## 5. Workflows

- [x] 5.1 Add `.github/workflows/check.yml` on `pull_request`: checkout with `fetch-depth: 0`, install `uv`, run `check --base origin/${{ github.base_ref }} --format github` and `index --dry-run`, and fail if the diff touches `index.json` and the PR author is not the CI app; verify with a test PR that has a deliberately bad persona (the check fails with an annotation on the file) and then a fixed one (the check passes)
- [x] 5.2 Add `.github/workflows/index.yml` on `push` to the default branch, with paths `personas/**`, `prompts/**`, `schema/**` and `tools/**` (never `index.json`), plus `workflow_dispatch` and `concurrency: { group: index, cancel-in-progress: false }`. It generates, then when `--changed` reports a change, commits `index.json` with GraphQL `createCommitOnBranch` (with `expectedHeadOid`) using a `PSW_CI_APP_ID` / `PSW_CI_PRIVATE_KEY` app token; verify the first merge produces a verified bot commit adding `index.json` and that commit does not start another run
- [x] 5.3 Confirm the `PSW_CI_APP_ID` and `PSW_CI_PRIVATE_KEY` secrets exist on Knot-Library and the app is installed on the repository; verify with `gh secret list -R pilgrimagesoftware/Knot-Library` and a successful `workflow_dispatch` run
- [x] 5.4 Describe both workflows in `CONTRIBUTING.md` (why the index is never edited by hand, and how to re-run the regeneration); verify the doc links resolve on GitHub

## 6. Seed content

- [x] 6.1 Port Knot-App's seven built-in personas from `crates/knot-core/src/consts.rs` `DEFAULT_PERSONAS` into `personas/`, keeping their UUIDs in lowercase form (`a1000001-0000-0000-0000-00000000000N`), copying the instructions verbatim, and adding a description and tags to each; verify `check` passes and each id matches the app's constant case-insensitively
- [x] 6.2 Add three example prompts in `prompts/` (for example code review, standup summary and handoff notes), at least one using `{{folder.name}}` or `{{branch}}`; verify `check` passes with no warnings
- [x] 6.3 Remove the `.gitkeep` files from seeded directories; verify `git ls-files personas prompts` lists only `.md` files

## 7. End-to-end verification

- [x] 7.1 After the change merges, verify the published contract from outside: fetch the raw `index.json`, check it lists 7 personas and 3 prompts, fetch one item at the index's `commit` and match its SHA-256, then repeat the index request with `If-None-Match` and get HTTP 304
- [x] 7.2 Merge a follow-up PR that edits one persona's description, and verify that a new index commit appears with the updated description and a new `sha256` for that item only
