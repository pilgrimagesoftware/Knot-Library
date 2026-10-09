# Making your own library

Knot can import personas and prompts from any library that uses this
repository's format, not just from Knot-Library. You might want one for a
team's shared personas, for prompts you don't want to publish, or to try
items out before you contribute them here.

> **Status:** Knot's support for libraries other than Knot-Library is
> proposed in
> [Knot-App#214](https://github.com/pilgrimagesoftware/Knot-App/pull/214)
> and has not shipped yet. The format and tools described here work today.

## What a library is

A library is a directory that holds:

- `index.json` at its root, which lists every item with its size and SHA-256
- the item files the index lists, one Markdown file per item, under a
  directory per kind (`personas/`, `prompts/`)

Knot reads the index first, then reads only the items you choose to import.
Before importing an item, it checks that the item's bytes match the hash in
the index.

Knot can read a library from three kinds of location:

| Location | You give Knot | Knot reads |
| --- | --- | --- |
| GitHub repository | `owner/repo`, and a branch if it isn't the default | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/index.json`, then each item at the commit the index names |
| Web address | the `https://` URL of the directory that holds `index.json` | `<url>/index.json`, then `<url>/<path>` for each item |
| Folder | a directory on your computer | `<folder>/index.json`, then `<folder>/<path>` for each item |

## Create one

You need [git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/).

1. Make a new git repository. A library has to be a git repository when you
   generate its index, because the index records the commit its content came
   from.

   ```sh
   mkdir my-library && cd my-library
   git init
   ```

2. Copy `schema/` and `tools/` from this repository into it. The tool reads
   the kinds and their schemas from `schema/`, so it needs both.
   `tools/tests/` is optional.

3. Add items under `personas/` and `prompts/`. Each one follows the same rules
   as an item contributed here; see [Adding an item](../CONTRIBUTING.md#adding-an-item)
   and [Front matter rules](../CONTRIBUTING.md#front-matter-rules). For
   example, `personas/release-captain.md`:

   ```markdown
   ---
   id: 6f1e2d3c-4b5a-4987-8a6b-5c4d3e2f1a0b
   title: Release Captain
   description: "Ships on schedule: small batches, green builds, and a written rollback plan."
   tags: [release]
   ---

   Keep every change releasable. Before merging, say how it would be rolled back.
   ```

   Give every item a new UUID. Knot identifies an item by its `id` across
   every library, so an id copied from Knot-Library makes your item the same
   item as that one: anyone who already has it sees yours as already
   imported.

4. Check the items:

   ```sh
   uv run tools/library.py check
   ```

## Generate the index

Commit your items first, then generate the index, then commit the index:

```sh
git add personas prompts
git commit -m "Add release captain"
uv run tools/library.py index
git add index.json
git commit -m "Regenerate index.json"
```

The order matters for a GitHub library. The index's `commit` is the commit
you were on when you generated it, and Knot fetches each item from that
commit. If you generate the index with uncommitted changes, it names a
commit that doesn't have those bytes, and Knot reports the items as
unreadable.

Regenerate and commit the index after every change to an item. To see
whether it's out of date, run `uv run tools/library.py index --changed`; it
exits 0 when the index needs regenerating and 1 when it's current.

### Automating it on GitHub

This repository's workflows can do the checking and indexing for you:

- [`.github/workflows/check.yml`](../.github/workflows/check.yml) checks
  every pull request. It needs no secrets, so you can copy it as it is.
- [`.github/workflows/index.yml`](../.github/workflows/index.yml)
  regenerates the index after each merge. It commits through a GitHub App
  that only Pilgrimage repositories have. To use it in your own repository,
  delete the `actions/create-github-app-token` step, set the job's
  permissions to `contents: write`, and change the commit step's `GH_TOKEN`
  to `${{ github.token }}`. If a branch ruleset requires pull requests on
  your default branch, allow GitHub Actions to bypass it, or keep
  regenerating the index by hand.

## Publish it

- **GitHub.** Push the repository. Knot reads it anonymously, so it has to
  be public. For a private library, use a local clone as a folder location.
- **Web server.** Serve the library directory as static files over
  `https://`, with `index.json` at the URL you give Knot and each item at
  the path the index lists. Knot doesn't accept plain `http://`.
- **Folder.** Nothing to publish. Point Knot at the directory.

## Use it in Knot

1. Open the Import window: **File > Import…**, or **Import from Library…**
   in the Personas or Prompts window.
2. In the **Library** section, choose **Add Location**. Give the library a
   name, pick its kind, and enter the repository, the web address or the
   folder.
3. Choose the library in the section's picker. Knot reads its index and
   lists its personas and prompts.
4. Tick the items you want and import them.

A persona's instructions and a prompt's text go into what your agents are
told, so only add libraries you trust.

Knot remembers saved locations, and you can rename or remove them from the
same section. Removing a location doesn't remove anything you imported from
it. Knot-Library is always available and can't be removed.

## Changing items later

- **Never change an item's `id`** once someone may have imported it, and
  never reuse an id. The rules in
  [CONTRIBUTING.md](../CONTRIBUTING.md#front-matter-rules) apply to your
  library too.
- Knot doesn't update an item that has already been imported. To get a
  newer version, delete the persona or prompt in Knot and import it again.

## Troubleshooting

| What Knot says | Why | Fix |
| --- | --- | --- |
| It couldn't reach the library | Wrong address, the repository is private, or no network | Check the location, and open `index.json` in a browser at the address Knot uses |
| An item is unreadable | Its bytes don't match the index: the item changed after the index was generated, or a GitHub index names a commit without them | Commit the items, regenerate the index, commit it |
| The library needs a newer Knot | The index's `format` is newer than your Knot supports | Update Knot, or generate the index with the tool version your Knot supports |
| An item is already in Knot | Knot has a persona or prompt with that `id`, perhaps from another library | Expected, unless you copied an id; give your item a new UUID |
