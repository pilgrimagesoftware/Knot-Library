---
id: 399d4053-a1e4-4266-a847-de5afadb4caa
title: Code review
description: Review the changes on the current branch for correctness, clarity and missing tests.
tags: [review, quality]
---

Review the changes on branch {{branch}} in {{folder.name}} against the branch it was cut from.

For each problem you find, give the file and line, say what is wrong and why it matters, and suggest a fix. Order the findings by severity: bugs and data loss first, then security, then missing or weak tests, then readability. Skip style points a formatter or linter would catch.

Finish with a one-line verdict: ready to merge, or what must change first.
