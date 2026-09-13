---
name: knowledge-workspace-operations
description: Use for notes, files, tables, and workspace services.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [productivity, notes, files, tables, workspace, integrations]
---

# Knowledge Workspace Operations

Use this umbrella to read, search, create, update, and organize knowledge across local vaults and hosted workspace services. Route by the system that owns the target data.

## Routing

- Airtable bases, tables, schemas, formulas, and records: `references/airtable/SKILL.md`.
- Box files, folders, search, bulk operations, events, and APIs: `references/box/SKILL.md`.
- Gmail, Calendar, Drive, Contacts, Sheets, and Docs: `references/google-workspace/SKILL.md`.
- Notion pages, data sources, Markdown, files, and Workers: `references/notion/SKILL.md`.
- Filesystem-first Obsidian vault notes and wikilinks: `references/obsidian/SKILL.md`.

## Shared workflow

1. Resolve the target service, account or vault, object type, exact identifier, and requested operation.
2. Read the selected branch's nested `SKILL.md`; complete its authentication or path setup without exposing secrets.
3. Inspect the target and schema before constructing writes. Preserve identifiers exactly as supplied.
4. Prefer reversible operations, explicit fields, bounded pagination, and provider-native concurrency controls.
5. For mutations, state the exact target and payload, perform the write once, then read back that exact object before claiming success.
6. Keep service facts distinct from local assumptions; permission failures and missing sharing grants are not proof an object does not exist.
7. Report affected object IDs or paths, verification results, and any unresolved permission or platform constraint.

Each provider remains a complete package under `references/<provider>/`; resolve internal relative links from that nested package root.