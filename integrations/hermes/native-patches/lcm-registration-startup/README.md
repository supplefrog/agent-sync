# LCM registration startup repair

Hermes bounds plugin import and registration to 10 seconds. LCM previously opened SQLite storage during registration; its legitimate writer wait can last 30 seconds. The host could abandon the worker and reject its later engine registration.

This repair registers the existing engine without opening storage. Activation initializes storage once; unload of an unused engine opens no database. Partial activation failure closes handles and permits a retry. Existing clone and unload guards remain in force.

The full affected test set passed 796 tests with three platform skips. The original native deadline failed under a held DB writer and passed after repair, followed by real ingest/readback. Ruff 0.15.13, syntax and whitespace checks passed. No provider call is part of these tests.

The manifest pins the installed source and patch. Recovery retains full current engine and entrypoint source; the patch additionally includes the regression tests. This branch includes the pre-existing installed Windows repairs. First use may still wait for a writer. Changing branch or channel can leave a local fix; restart existing Hermes processes to load it.
