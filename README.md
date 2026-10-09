# Knot Library

A shared library of personas and prompts for [Knot](https://github.com/pilgrimagesoftware/Knot-App).
Knot can browse it and import items into your own settings.

## What is in it

| Kind | Directory | What it is |
| --- | --- | --- |
| `persona` | [`personas/`](personas/) | Instructions that shape how an agent works, such as "Kent Beck" or "Orchestrator". |
| `prompt` | [`prompts/`](prompts/) | Reusable prompts you send to an agent. They can use Knot's `{{...}}` variables. |

Each item is one Markdown file. The YAML front matter holds the item's id,
title, description and tags, and the body holds the persona's instructions
or the prompt's text. The directory gives the kind, and the file name gives
the item's slug. [`schema/kinds.json`](schema/kinds.json) lists the kinds,
and [`schema/`](schema/) holds a JSON Schema for each.

## The index

Every item is listed in one file, which clients can fetch in a single request:

    https://raw.githubusercontent.com/pilgrimagesoftware/Knot-Library/master/index.json

Each entry gives the item's kind, id, slug, title, description, tags,
authors, path, size and SHA-256. The index's `commit` field names the commit
its content was read from. To fetch an item and check its hash, use that
commit in the URL:

    https://raw.githubusercontent.com/pilgrimagesoftware/Knot-Library/<commit>/<path>

[`schema/index.schema.json`](schema/index.schema.json) describes the format.
The index is generated after every merge and is never edited by hand.

## Your own library

You don't have to publish here to share items. A library is any directory
with this layout and a generated `index.json`, and Knot can import from one
on GitHub, on a web server or in a folder on your computer.
[Making your own library](docs/your-own-library.md) explains how to create
one, generate its index, and add it to Knot.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The content is licensed under [CC BY 4.0](LICENSE.md).
