# Design

## Context

Knot-Library is an empty public repository: `master` is its only branch, and
it holds nothing but OpenSpec scaffolding. There is no LICENSE file and no
branch ruleset. See proposal.md for motivation.

The content has to match what Knot-App already models
(`crates/knot-core/src/settings/records.rs`, `settings/prompts.rs`):

- `Persona { id: Uuid, name, instructions, type: system|user, state }`. No
  description, tags or avatar. Seven built-in personas ship with fixed UUIDs
  `a1000001-0000-0000-0000-00000000000N`.
- `Prompt { id: Uuid, name, text }`, plus a closed set of `{{...}}` variables
  that are expanded when the prompt is sent.
- Knot's existing import (`data-import` spec) is additive and idempotent, and
  de-duplicates subagent personas by name. Its records are identified by
  UUID.

The library therefore keys items by UUID too, and adds `description`, `tags`
and `authors` as library-side metadata that Knot can show while browsing,
without needing to store it.

## Goals / Non-Goals

**Goals:**
- Content that is easy to write and to review in a pull request diff.
- A client lists the whole library with one request and fetches only what it
  imports, each file verified by hash.
- No server to run: GitHub hosts and serves everything.

**Non-Goals:**
- Knot's import UI and its mapping code, which is a Knot-App change that
  consumes this format.
- Private or authenticated libraries, several library sources, search
  ranking, ratings, or download counts.
- Agent (bench) templates and workspaces as kinds. The format leaves room for
  them, but each needs its own design: templates refer to personas and
  prompts by id, and that reference model belongs in the template change.
- Localized content. Knot never localizes persona or prompt text either.

## Decisions

### Markdown with YAML front matter, one file per item
Persona instructions and prompts are long prose, so Markdown bodies diff
well and render on GitHub. Claude Code subagent files, which Knot already
imports, use the same front-matter-plus-body shape.
- *Rejected: one JSON file per kind.* Every contribution would edit the same
  file, causing merge conflicts and unreadable diffs of escaped strings.
- *Rejected: JSON or YAML per item.* Multi-line text would need escaping or
  block scalars, which are easy to get wrong in review.

### Directory names the kind; the file name is the slug
`personas/kent-beck.md` gives readable URLs and makes a kind's items easy to
browse on GitHub. The kind is not repeated in front matter, so a file can
never disagree with its directory. A small registry, `schema/kinds.json`,
maps each kind name (singular, e.g. `persona`) to its directory (plural, e.g.
`personas`) and its schema file. Adding a kind is a registry entry, a
directory and a schema.

### UUID `id` in front matter, slug only for paths
Knot's records are keyed by UUID, so the item `id` is the identity an import
keeps, and a re-import updates the record instead of duplicating it. Slugs
can change for readability without breaking clients. The seven built-in
personas keep their shipped UUIDs, so importing the library copy of "Kent
Beck" matches the built-in record instead of adding a second one.
- *Rejected: the slug as identity.* Renames would orphan imported copies, and
  slugs don't match Knot's model.

### A committed `index.json`, regenerated after merge
The index lives on the default branch beside the content, so the raw URL is
stable, GitHub's CDN serves it with an `ETag`, and every commit carries the
index that matches it. A workflow on `push` to the default branch rebuilds
it, with path filters on `personas/**`, `prompts/**`, `schema/**` and
`tools/**`, plus `workflow_dispatch`. `concurrency: index` with
`cancel-in-progress: false` serializes runs, and each run regenerates from
the branch head, so the last run's index always describes everything merged.
- *Rejected: contributors regenerate the index in their pull request.* Any
  two open PRs would conflict on `index.json`, and a stale index could merge.
- *Rejected: publishing the index as a release asset or through GitHub
  Pages.* That adds deploy machinery and a second URL scheme. The asset would
  also not be tied to a commit unless every merge cut a release.
- *Rejected: the GitHub Contents or Trees API from Knot.* One request per
  file, and the unauthenticated limit is 60 requests an hour.

### The index commits through the GitHub API as the PSW CI app
The workflow mints a token with `actions/create-github-app-token` (the
`PSW_CI_APP_ID` and `PSW_CI_PRIVATE_KEY` secrets used across Pilgrimage
repositories) and commits with GraphQL `createCommitOnBranch`. Commits made
that way are signed by GitHub, so a later `required_signatures` rule still
passes, and the app can be the only bypass actor if a ruleset is added. A
commit made with `GITHUB_TOKEN` would not trigger workflows, but this one
must not anyway. Instead, `index.json` is left out of the path filter, so the
index commit can never trigger another regeneration.

### `commit` is the content commit, and the index only commits on real change
`commit` is the SHA the content was read from, not the later index commit.
Items are fetched at that SHA, which gives immutable URLs: a client that
cached the index can keep fetching consistent files after newer merges. The
workflow compares only `items` and `kinds` with the committed index, so a
change that doesn't touch content (a schema comment, say) doesn't produce a
commit just to update the timestamp. When nothing changed, the old `commit`
still names a tree with identical item bytes, so it stays valid.

### Hashes of exact file bytes
`sha256` and `size` cover the raw file, front matter included, so clients
verify exactly what they downloaded without parsing it first. Git's own blob
SHA-1 was considered, but clients would have to rebuild git's
`blob <len>\0` header to check it. SHA-256 of the plain bytes is simpler and
stronger.

### Tooling: one Python script, run with `uv`
`tools/library.py` has two subcommands: `check` (validate, plus the base-branch
identity rules when given `--base`) and `index` (generate). It declares its
dependencies, PyYAML and `jsonschema`, as PEP 723 inline metadata, and is run
as `uv run tools/library.py ...`, so there is no project environment or lock
file to maintain, and the local command matches CI exactly. YAML is parsed
with the safe loader and must be a mapping. Values are checked against the
published JSON Schemas (draft 2020-12), then the cross-file rules (unique
ids, unique slugs, flat directories) run in the script.
- *Rejected: Rust, matching Knot-App.* That would mean compiling a toolchain
  in CI for a content repository, and contributors may not have one.
- *Rejected: Node with a front-matter package.* A larger dependency tree for
  the same result.

### Ids of deleted items stay retired
The identity check reads deleted items' ids from git history
(`git log --diff-filter=D`, reading each deleted file at its parent commit)
with `fetch-depth: 0`. The repository holds small text files, so a full
clone stays cheap.
- *Rejected: a committed list of retired ids.* That is another file that
  contributors could forget or edit by hand.

### Pull-request checks
`.github/workflows/check.yml` runs on `pull_request`. It runs
`library.py check --base origin/<base>` and `library.py index --dry-run`,
emits `::error file=...,line=...::` annotations, and fails when the diff
touches `index.json` and the author is not the CI app.

## Risks / Trade-offs

- [The index commit fails, for example because the app's secrets are missing
  or the branch is protected without a bypass] → The workflow fails visibly,
  `workflow_dispatch` re-runs it once fixed, and Knot keeps serving the
  previous index, which stays internally consistent.
- [GitHub's raw CDN caches `index.json` for a few minutes after it changes] →
  That's acceptable for a browse list. Knot can show `generatedAt`, and pinned
  item fetches are unaffected.
- [The single index grows large] → Each entry is a few hundred bytes, so even
  2,000 items is about 0.5 MB, fetched only when the `ETag` changes. If it
  ever matters, a later format can shard by kind, behind a `format` bump.
- [A contributor's PR merges between a regeneration's checkout and its
  commit] → `createCommitOnBranch` takes `expectedHeadOid` and fails if the
  head has moved. The queued run that the newer push started then
  regenerates from the new head.
- [Seeded built-in personas drift from the copies shipped in Knot-App] → The
  library is the shareable copy, not the source of Knot's defaults. Whether
  Knot's "restore defaults" should ever read the library is left to the
  import change.

## Migration Plan

This is a new repository with no content, so there is nothing to migrate.
Land the format, schemas, tooling and workflows in one pull request together
with the seed content; the first push to the default branch produces the
first `index.json`. To roll back, revert the pull request. No client depends
on the index until Knot-App's import change ships.

## Open Questions

- Default branch name: GitHub has `master`, while the split-repositories
  design said `main`. The workflows use `github.event.repository.default_branch`
  and need no change either way, but the raw index URL that Knot hard-codes
  needs the final name before the import change.
- LICENSE: the split-repositories design specifies CC BY 4.0, but the file
  isn't in the repository. Seeded content should land under a license, so
  adding it is a task here unless that change does it first.
