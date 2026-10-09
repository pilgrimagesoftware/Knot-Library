# content-index Specification

## Purpose
Gives Knot one small, machine-generated document listing everything in the
library, so it can show titles and descriptions without walking or
downloading the repository's content.

## Requirements

### Requirement: Index document
The repository SHALL contain `index.json` at its root: a UTF-8 JSON object
with camelCase keys:

- `format`: the integer index format version, `1` for this change.
- `commit`: the full SHA of the commit whose content the index describes.
- `generatedAt`: when the index was generated, in RFC 3339 UTC.
- `kinds`: an object with one entry per registered kind, keyed by kind name,
  giving the kind's `directory` and its item `count`.
- `items`: an array with one entry per item.

Each entry in `items` SHALL contain `kind`, `id`, `slug`, `title`,
`description`, `tags` (empty when the item has none), `authors` (empty when
the item has none), `path` (repository-relative, `/`-separated), `size` (the
file's length in bytes) and `sha256` (the lowercase hex SHA-256 of the
file's exact bytes). Entries SHALL NOT contain item bodies.

#### Scenario: Browse list from one request
- **WHEN** a client fetches `index.json`
- **THEN** it has every item's kind, title and description without fetching any other file

#### Scenario: Bodies stay out of the index
- **WHEN** a persona's instructions run to several kilobytes
- **THEN** its index entry is the same size as for a short persona, apart from its metadata

### Requirement: Deterministic output
Generating the index twice from the same content SHALL produce
byte-identical `items` and `kinds`. Items SHALL be ordered by kind name, then
by slug. The JSON SHALL use two-space indentation, a trailing newline and a
fixed key order.

#### Scenario: No-op regeneration
- **WHEN** the index is regenerated with no content changes since the last generation
- **THEN** `items` and `kinds` are unchanged and no commit is made

### Requirement: Index regenerated on merge
After any push to the default branch that changes content, a kind's schema,
the kind registry or the index tooling, a workflow SHALL regenerate
`index.json` from that commit and commit the result to the default branch if
`items` or `kinds` changed. The workflow SHALL be runnable on demand, and
runs SHALL be serialized so that two merges cannot commit indexes out of
order. Committing the index SHALL NOT trigger another regeneration.

#### Scenario: New persona merged
- **WHEN** a pull request adding `personas/dave-farley.md` merges
- **THEN** within that workflow run the default branch gets a commit updating `index.json` to include the persona, with `commit` set to the merge commit's SHA

#### Scenario: Unrelated change
- **WHEN** a commit changes only `README.md`
- **THEN** no index regeneration runs

#### Scenario: Two merges close together
- **WHEN** two content pull requests merge within seconds of each other
- **THEN** the final `index.json` on the default branch describes both items

### Requirement: Index is never hand-edited
`index.json` SHALL change only through the regeneration workflow.
Contributors SHALL NOT include changes to it in pull requests.

#### Scenario: Pull request edits the index
- **WHEN** a pull request from a contributor modifies `index.json`
- **THEN** the contribution checks fail and explain that the index is generated after merge

### Requirement: Fetching an item
A client SHALL be able to fetch any listed item at
`https://raw.githubusercontent.com/pilgrimagesoftware/Knot-Library/<commit>/<path>`,
using the index's `commit` and the entry's `path`. Because the URL names a
commit, the file's bytes SHALL match the entry's `sha256` and `size`. A
client SHALL reject an item whose bytes do not match.

#### Scenario: Pinned fetch
- **WHEN** a client fetches an item using the index's `commit`, after newer content has merged
- **THEN** it receives exactly the version the index describes, matching `sha256`

#### Scenario: Tampered or truncated download
- **WHEN** the downloaded bytes' SHA-256 differs from the index entry
- **THEN** the client discards the item and reports it as unavailable

### Requirement: Cheap refresh
The index SHALL be served at a stable URL on the default branch,
`https://raw.githubusercontent.com/pilgrimagesoftware/Knot-Library/<default-branch>/index.json`,
so that a client can repeat a conditional request with the previous
response's `ETag` and get a not-modified response when nothing changed.

#### Scenario: Nothing new
- **WHEN** Knot re-fetches the index with `If-None-Match` set to the `ETag` it last received, and the index has not changed
- **THEN** it gets HTTP 304 and keeps its cached list

### Requirement: Forward compatibility
A client SHALL ignore index entries whose `kind` it does not recognise and
item-entry fields it does not recognise. A change that removes or changes the
meaning of an existing field SHALL increment `format`; adding fields or kinds
SHALL NOT.

#### Scenario: Older client, newer kind
- **WHEN** a Knot release that knows only `persona` and `prompt` reads an index that also lists `template` items
- **THEN** it lists the personas and prompts and skips the templates without error
