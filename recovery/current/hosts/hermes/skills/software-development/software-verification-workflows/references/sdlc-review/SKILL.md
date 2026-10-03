# Native Kanban review preload

Hermes review dispatch passes `--skills sdlc-review` to the worker. The review procedure therefore lives at the discoverable native entrypoint `devops/sdlc-review/SKILL.md`; load it with `skill_view(name="sdlc-review")`.

Support files beneath this verification router are excluded from skill discovery. This file records the preload boundary; it contains no separate review procedure. If startup reports that `sdlc-review` is missing or disabled, repair the selected profile's native entrypoint or enablement before dispatching its review work. Loading the router alone does not preload the review procedure.
