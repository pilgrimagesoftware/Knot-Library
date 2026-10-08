# Spec Delta

## Purpose

Validates every pull request against the content format before it can merge,
so the default branch always holds content Knot can import and an index that
can be regenerated from it.

## ADDED Requirements

### Requirement: Pull requests are validated
Every pull request to the default branch SHALL run the contribution checks,
which validate every item in the resulting tree against the content format.
Any error SHALL fail the check. Warnings SHALL be reported without failing
it.

#### Scenario: Valid contribution
- **WHEN** a pull request adds a well-formed prompt
- **THEN** the check passes

#### Scenario: Invalid contribution
- **WHEN** a pull request adds a persona whose front matter has no `description`
- **THEN** the check fails

### Requirement: Actionable error reports
Each error and warning SHALL name the file and, where one applies, the front
matter field or line, together with the rule it breaks. On GitHub, errors
SHALL appear as annotations on the offending file in the pull request.

#### Scenario: Annotated failure
- **WHEN** `prompts/standup.md` has a `title` longer than 80 characters
- **THEN** the pull request shows an error annotation on `prompts/standup.md` naming `title` and the 80-character limit

### Requirement: Identity rules checked against the base
The checks SHALL compare the pull request with its base branch and fail when
an existing item's `id` changes, or when a new item's `id` matches an item
that the base branch has or had at any point in its history.

#### Scenario: Changed id
- **WHEN** a pull request edits `personas/kent-beck.md` and changes its `id`
- **THEN** the check fails, saying ids are permanent

#### Scenario: Reused id of a deleted item
- **WHEN** a pull request adds an item whose `id` belonged to an item deleted in an earlier commit
- **THEN** the check fails, naming the commit that deleted the original

### Requirement: Generated index protected
The checks SHALL fail any pull request that modifies `index.json`, unless the
pull request was opened by the index-regeneration workflow's own identity.

#### Scenario: Contributor edits index
- **WHEN** a contributor's pull request includes a change to `index.json`
- **THEN** the check fails and tells them to drop the change

### Requirement: Index stays generatable
The checks SHALL generate an index from the pull request's tree without
publishing it, and fail if generation fails.

#### Scenario: Generation would fail
- **WHEN** a pull request leaves two items in the same kind with the same slug, for example through a case-only rename on a case-insensitive file system
- **THEN** the check fails before merge instead of the post-merge workflow failing

### Requirement: Runnable locally
Contributors SHALL be able to run the same checks locally with a single
documented command, getting the same results as CI.

#### Scenario: Local run
- **WHEN** a contributor runs the documented validation command in a clone
- **THEN** they get the same errors and warnings the pull request check would report
