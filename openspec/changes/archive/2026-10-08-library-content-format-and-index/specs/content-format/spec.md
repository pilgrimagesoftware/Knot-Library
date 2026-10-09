# Spec Delta

## Purpose

Defines how shareable Knot content (personas, prompts and future kinds) is
laid out and described in the Knot-Library repository, so contributors know
what to write and Knot knows what it can import.

## ADDED Requirements

### Requirement: One file per item, one directory per kind
Each library item SHALL be a single UTF-8 Markdown file in the top-level
directory named for its kind: `personas/` for personas, `prompts/` for
prompts. Items SHALL NOT be nested in subdirectories of a kind directory. A
file's name SHALL be its slug followed by `.md`.

#### Scenario: A persona file
- **WHEN** a contributor adds the persona "Kent Beck"
- **THEN** it lives at `personas/kent-beck.md`

#### Scenario: A nested file is rejected
- **WHEN** a file is added at `personas/classic/kent-beck.md`
- **THEN** validation fails, naming the file and saying that kind directories are flat

### Requirement: Slugs
A slug SHALL be 1 to 64 characters of lowercase ASCII letters, digits and
single hyphens, starting and ending with a letter or digit. Slugs SHALL be
unique within a kind; the same slug MAY appear in two different kinds.

#### Scenario: Invalid slug
- **WHEN** a file is named `personas/Kent_Beck.md`
- **THEN** validation fails, naming the file and the slug rule it breaks

#### Scenario: Same slug, different kinds
- **WHEN** `personas/reviewer.md` and `prompts/reviewer.md` both exist
- **THEN** both are valid

### Requirement: Item envelope
Every item SHALL begin with a YAML front matter block delimited by `---`
lines. All kinds share these front matter fields:

- `id` (required): a UUID in canonical lowercase hyphenated form.
- `title` (required): 1 to 80 characters, one line. Knot shows it as the item's name.
- `description` (required): 1 to 200 characters, one line, plain text. Knot shows it in lists.
- `tags` (optional): a list of up to 10 tags, each 1 to 32 characters of
  lowercase letters, digits and hyphens, with no duplicates.
- `authors` (optional): a list of credits, each a GitHub handle (`@name`) or a free-text name.

A kind MAY define more fields in its own schema. Front matter fields that
neither the envelope nor the item's kind defines SHALL be rejected.

#### Scenario: Minimal valid item
- **WHEN** an item's front matter has only `id`, `title` and `description`, and its body is not empty
- **THEN** the item is valid

#### Scenario: Unknown field
- **WHEN** an item's front matter contains `colour: blue` and the kind does not define `colour`
- **THEN** validation fails, naming the field

#### Scenario: Multi-line description
- **WHEN** an item's `description` contains a line break
- **THEN** validation fails

### Requirement: Item body
Everything after the closing front matter delimiter SHALL be the item's
content, with leading and trailing whitespace trimmed. The trimmed body SHALL
NOT be empty. The body is stored and delivered exactly as written; it SHALL
NOT be localized, templated or rewritten by library tooling.

#### Scenario: Empty body
- **WHEN** an item has valid front matter and nothing but whitespace after it
- **THEN** validation fails, naming the file

### Requirement: Stable item identity
An item's `id` SHALL be unique across the whole library, regardless of kind.
Once merged, an item's `id` SHALL NOT change, including when the item's
title, slug or file name changes. A deleted item's `id` SHALL NOT be reused
by another item.

#### Scenario: Duplicate id
- **WHEN** two files declare the same `id`
- **THEN** validation fails, naming both files

#### Scenario: Rename keeps id
- **WHEN** `personas/uncle-bob.md` is renamed to `personas/robert-martin.md` with the same `id`
- **THEN** the item is valid and clients treat it as the same item

### Requirement: Persona kind
A persona SHALL use the item envelope with no additional front matter
fields. Its body SHALL be the persona's instructions, which Knot imports as
`Persona.instructions`, with `title` imported as `Persona.name`.

#### Scenario: Persona maps onto Knot's record
- **WHEN** Knot imports a persona item
- **THEN** it gets a persona whose id is the item's `id`, whose name is `title` and whose instructions are the body

### Requirement: Prompt kind
A prompt SHALL use the item envelope with no additional front matter fields.
Its body SHALL be the prompt text, which Knot imports as `Prompt.text`, with
`title` imported as `Prompt.name`. The body MAY use Knot's prompt variables,
`{{agent.name}}`, `{{agent.id}}`, `{{agent.type}}`, `{{folder}}`,
`{{folder.name}}`, `{{workspace}}`, `{{branch}}` and `{{date}}`; `\{{`
writes a literal `{{`. A `{{name}}` reference outside that set SHALL produce
a validation warning that does not fail the check.

#### Scenario: Known variable
- **WHEN** a prompt body contains `Review the changes in {{folder.name}}`
- **THEN** the item is valid with no warnings

#### Scenario: Unknown variable
- **WHEN** a prompt body contains `{{repo}}`
- **THEN** the item is valid and validation reports a warning naming `{{repo}}`

### Requirement: Extensible kinds
Adding a kind SHALL require only a new top-level directory and a JSON Schema
for that kind's front matter, registered in the library's kind registry. The
index format SHALL NOT change when a kind is added. A client SHALL be able to
skip index entries of kinds it does not recognise.

#### Scenario: New kind added
- **WHEN** a `templates` kind is registered with its schema and `templates/` holds items
- **THEN** those items appear in the index with `kind` set to `template`, and the index's format version is unchanged

### Requirement: Published schemas
The repository SHALL publish a JSON Schema for each kind's front matter and
one for `index.json`, at stable paths under `schema/`. Validation SHALL use
these same schemas.

#### Scenario: Schema available to clients
- **WHEN** a client wants to validate a persona's front matter
- **THEN** it can fetch `schema/persona.schema.json` from the repository at any commit
