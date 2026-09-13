---
name: apple-ecosystem-automation
description: Operate Apple personal-data and communication services on macOS, including Notes, Reminders, Find My devices/AirTags, and iMessage/SMS. Use whenever a user asks to create/search/edit Apple notes, manage reminders, locate Apple hardware, or send/read Messages.
---
# Apple ecosystem automation

Use the service-specific reference for exact commands and prerequisites. These tools require macOS and may require Automation, Accessibility, Contacts, or Full Disk Access permissions.

## Routing
- Notes: read `references/apple-notes.md`.
- Reminders: read `references/apple-reminders.md`.
- Find My devices/AirTags: read `references/findmy.md`.
- iMessage/SMS: read `references/imessage.md`.

## Shared safety
1. Verify the relevant CLI exists and permissions are granted.
2. Resolve ambiguous lists, accounts, recipients, or devices before a write/send action.
3. Read back created or edited records when the CLI supports it.
4. Treat message sends, reminder completion/deletion, and note deletion as external side effects; report the concrete result.