# LCM hook ownership and manifest wording

This additive native patch records two reviewed source corrections. `__init__.py` registers `post_llm_call` through the current Hermes `PluginContext.register_hook` API so targeted unload removes the exact callback. The direct manager append remains only as compatibility for older hosts without that API. `plugin.yaml` now describes persistence and structured retrieval without claiming that the plugin can never lose a message.

Restore the upstream checkout at the exact base revision in `manifest.json`. Preserve or independently apply `lcm-session-transactions`; its engine/assertion changes do not overlap these files. Verify both `before_sha256` values, run `git -c core.autocrlf=false -c core.whitespace=cr-at-eol apply --check repair.patch`, apply with the same options, and verify both `after_sha256` values. Stop on any mismatch.

The candidate passed a fresh installed Hermes `PluginManager` load, unload, reload, and unload cycle with hook counts `1, 0, 1, 0`. The callback was not invoked, all state was synthetic, and no personal database or model/provider call occurred.

The source edit does not retroactively own callbacks already appended in an existing process. Start a fresh Hermes process to observe the corrected lifecycle. This record is not a whole-plugin installer or recovery claim.
