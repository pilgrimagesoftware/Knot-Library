# Proposal

## Why

Knot-Library is meant to hold personas, prompt snippets and other content that
Knot users can import, but the repository has no defined layout yet, so
nothing can be contributed and the app has nothing to build an importer
against. The importer also needs a cheap way to list what is available: if
Knot had to walk the repository tree and download every file just to show
titles and descriptions, a browse screen would cost one request per item and
would hit GitHub's unauthenticated rate limit as soon as the library grows.

## What Changes

- **Define the content layout**: one Markdown file per item, grouped in one
  directory per kind (`personas/`, `prompts/`), with YAML front matter for
  the metadata and the body for the content itself.
- **Define a common item envelope** that every kind shares: a stable UUID
  `id`, `title`, a one-line `description`, `tags` and `authors`. The `id`
  lines up with the UUID identity Knot already uses for personas and prompts,
  so a re-import updates an item instead of duplicating it.
- **Define two kinds** that map directly onto existing Knot records:
  - **persona**: the body becomes the persona's instructions.
  - **prompt** (a "snippet" in the library's wording; Knot calls these
    library prompts): the body becomes the prompt text. It may use Knot's
    prompt variables (`{{agent.name}}`, `{{folder}}`, ...).
- **Make kinds extensible**: a new kind is a new directory plus a JSON Schema
  for its front matter, with no change to the index format. Agent (bench)
  templates are the expected next kind.
- **Publish JSON Schemas** for the front matter of each kind and for the
  index, so contributors' editors and Knot can validate against the same
  contract.
- **Generate a single `index.json`** at the repository root listing every
  item's kind, id, slug, title, description, tags, authors, path, size and
  SHA-256. Knot can show a full browse list from one request, then fetch only
  the items the user picks and check each one against its hash.
- **Regenerate the index automatically** with a GitHub Actions workflow that
  runs after content merges to the default branch and commits the updated
  index. Contributors never edit `index.json` by hand.
- **Validate pull requests** with a workflow that checks every item against
  its schema, enforces unique and immutable ids, and rejects hand edits to
  `index.json`.
- **Seed the library** with Knot's seven built-in personas, keeping their
  fixed UUIDs so an import recognises them, plus a few example prompts.

## Capabilities

### New Capabilities
- `content-format`: repository layout, the shared item envelope, the persona
  and prompt kinds, slugs and ids, and how new kinds are added.
- `content-index`: the `index.json` document, how it is generated, when it is
  published, and how a client uses it to list and fetch items.
- `contribution-checks`: the pull-request validation that keeps content and
  the index trustworthy.

### Modified Capabilities

None. The repository has no specs yet.

## Impact

- **Knot-Library** gains `personas/`, `prompts/`, `schema/`, `index.json`, a
  small validation and index tool under `tools/`, two workflows under
  `.github/workflows/`, and a `CONTRIBUTING.md`.
- **Knot-App** is not changed here. Its future import change will consume
  `index.json` and the item files, and map them onto its existing `Persona`
  (`name` and `instructions`) and `Prompt` (`name` and `text`) records.
- **CI identity**: the index workflow commits to the default branch, so it
  needs a token that can push there. The proposal reuses the PSW CI GitHub
  App that the other Pilgrimage repositories use; any future branch ruleset
  must allow that app to bypass it.
- **Repository basics this change depends on but does not decide**: the
  default branch is `master` on GitHub (the split-repositories design said
  `main`), and there is no LICENSE file yet (that design specifies CC BY 4.0).
  The workflows target the default branch whichever name it ends up with.
