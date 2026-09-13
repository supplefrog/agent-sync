# Hermes Desktop lifecycle / lazy-resume PR notes

Use when filing or implementing Desktop/gateway lifecycle fixes involving slow resume, stale busy state, image attach timeouts, or orphaned gateway workers.

## Durable pattern

When the user asks for both an issue and a PR, do not stop after creating/updating the issue. Continue through a focused fix, targeted tests, branch push, PR creation, and PR verification unless blocked by permissions or missing scope.

## Practical fix shape from the session

- Desktop chat resume should paint stored history first and defer full `AIAgent` construction until an operation actually needs the agent.
- Existing gateway lazy-session machinery can be reused for ordinary Desktop resume when the frontend passes `lazy: true` to `session.resume`.
- Local image staging should not force agent construction. `image.attach` can use the no-wait session lookup and only mutate queued attachments; `prompt.submit` can build/upgrade the agent later.
- On Windows, direct `child.kill()`/`Popen.terminate()` is not enough for Desktop/backend process trees. Use a tree-aware cleanup (`taskkill /PID <pid> /T /F`) for backend descendants and slash-worker close paths, with the existing direct-process termination as fallback.
- Before opening a duplicate orphan-process PR, inspect nearby open PRs. In this case a broader slash-worker lifecycle PR existed, so the new PR body should explicitly mark the relationship and boundary.

## Targeted verification examples

- Gateway image/worker tests:
  - `python -m pytest tests/test_tui_gateway_server.py::test_image_attach_does_not_wait_for_lazy_agent_build ... -q`
  - include worker-close tests covering POSIX direct kill, Windows `taskkill /T /F`, and fallback when `taskkill` is unavailable.
- Desktop validation:
  - `npm run typecheck` from `apps/desktop`
  - `node --test electron/backend-ready.test.cjs electron/desktop-uninstall.test.cjs electron/session-windows.test.cjs` from `apps/desktop`

## Pitfalls

- Do not treat a screenshot/image timeout as only an image bug if Desktop is still in agent initialization. Check whether resume/attachment RPCs are blocked behind agent build first.
- Do not conflate provider `Unsupported content type` with Desktop resume slowness. The Desktop fix is to decouple resume/attachment from agent build; deeper provider multimodal sanitization may need a separate issue/fix.
- If pushing to upstream fails with 403, push the branch to the authenticated fork remote and create the PR with `--head <user>:<branch>`.
