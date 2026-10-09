# Contributing

Each persona or prompt is a single Markdown file, so a pull request that adds
an item adds one file. Checks run on every pull request, and the index
updates itself once your change merges.

## Adding an item

1. Pick the directory for the kind: `personas/` or `prompts/`.
2. Name the file after the item's slug, for example `personas/grace-hopper.md`.
   A slug is 1 to 64 lowercase letters, digits and single hyphens, and it
   starts and ends with a letter or digit. Files sit directly in the kind
   directory, never in a subdirectory.
3. Begin the file with front matter, then write the content:

   ```markdown
   ---
   id: 0c5b2a3e-8f1d-4e7a-9b3c-2d1e0f9a8b7c
   title: Grace Hopper
   description: "Pragmatic and inventive: ship it, measure it, and ask forgiveness rather than permission."
   tags: [pragmatism, compilers]
   authors: [Your Name]
   ---

   The persona's instructions, or the prompt's text.
   ```

4. Run the check (see below) and open a pull request.

### Front matter rules

| Field | Required | Rule |
| --- | --- | --- |
| `id` | yes | A new UUID in lowercase hyphenated form. Generate one with `uuidgen \| tr A-Z a-z` or `python3 -c 'import uuid; print(uuid.uuid4())'`. |
| `title` | yes | 1 to 80 characters on one line. |
| `description` | yes | 1 to 200 characters on one line. |
| `tags` | no | Up to 10 distinct tags, each 1 to 32 lowercase letters, digits and hyphens. |
| `authors` | no | A list of names, each on one line. |

No other fields are allowed. Quote a value that contains `: ` or begins with
a character YAML treats specially, such as `[`, `{`, `&` or `*`. The body
after the front matter must not be empty.

- **Ids are permanent.** Knot keys what it imports by `id`, so changing an
  item's id makes it a different item for everyone who imported it. Never
  change the id of an item that has merged, and never reuse an id, not even
  that of a deleted item. The slug can change, since only paths use it.
- Ids are unique across the whole library, and slugs are unique within a kind.
- **Prompt variables.** A prompt can use Knot's variables, which Knot
  replaces when it sends the prompt: `{{agent.name}}`, `{{agent.id}}`,
  `{{agent.type}}`, `{{folder}}`, `{{folder.name}}`, `{{workspace}}`,
  `{{branch}}` and `{{date}}`. The check warns about any other `{{name}}`,
  since Knot would send it as written. Write `\{{` for a literal `{{`.

## Checking locally

The tool needs [uv](https://docs.astral.sh/uv/), which installs its
dependencies on first run:

    uv run tools/library.py check --base origin/master

`--base` applies the id rules against the default branch, so fetch it first
(`git fetch origin`). Without `--base`, only the format rules run. Errors fail
the check; warnings don't.

To preview the index your change would produce:

    uv run tools/library.py index --dry-run

The tool's own tests run with:

    uv run --with pytest --with pyyaml --with jsonschema pytest tools/tests

## Workflows

- **[Check](.github/workflows/check.yml)** runs on every pull request. It runs
  the check above against the pull request's base branch and reports each
  problem as an annotation on the offending file. It also confirms that the
  index can be generated, runs the tool's tests, and fails if the pull
  request edits `index.json`.
- **[Index](.github/workflows/index.yml)** runs after a merge to `master`
  that touches `personas/`, `prompts/`, `schema/` or `tools/`. It regenerates
  `index.json` and, when an item or kind actually changed, commits it as the
  PSW CI app.

### Why the index is never edited by hand

`index.json` lists every item with its size and SHA-256, and Knot uses those
hashes to verify what it downloads. If contributors updated it in their pull
requests, any two open pull requests would conflict over it, and a stale
index could merge. Instead, it is always generated from what is on `master`.
Leave it out of your pull request; the Check workflow fails if you include it.

### Re-running the regeneration

If an Index run fails (for example, because the app's secrets were missing),
fix the cause and then start the workflow again from the Actions tab:
**Index → Run workflow** on `master`, or:

    gh workflow run index.yml -R pilgrimagesoftware/Knot-Library

The run regenerates from the current head of `master`. It only commits when
`items` or `kinds` differ from the committed index.

## License

By contributing, you agree that your contribution is licensed under
[CC BY 4.0](LICENSE.md).
