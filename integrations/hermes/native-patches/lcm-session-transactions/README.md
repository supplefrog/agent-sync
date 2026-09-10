# LCM session and transaction repair

This is the source delta for the installed LCM repair. Native LCM remains the implementation owner. The patch and MIT license are retained here so local source changes are not lost during host recovery.

Prerequisites: restore the native LCM checkout at the exact base revision in `manifest.json`, its dependencies and Hermes plugin registration. That installation is outside Agent Sync's declarative restore. The recorded remote identifies the source repository; availability of every historical commit on a future remote is not guaranteed.

Before applying, compare every existing file with its `before_sha256`; an added file must be absent. Stop on unrelated source changes. From that native checkout, run `git -c core.autocrlf=false -c core.whitespace=cr-at-eol apply --check <absolute-path-to-repair.patch>`, then apply with the same Git options. These explicit settings preserve reviewed line endings. Verify every `after_sha256` from the manifest before starting a fresh Hermes process. To roll back this exact patch, verify the after hashes, run the reverse check and reverse apply. Preserve unrelated work.

Agent Sync records exact file readbacks for the two production modules. If the native prerequisite is absent or differs, recovery reports failure; it does not claim a whole agent was reconstructed. Tests, personal databases, credentials and existing sessions are not executed or read by this hash check.

The repair passed 189 distinct affected tests and seven fresh native plugin load/clone/behavior/unload checks using synthetic data. It does not provide cross-process lifecycle transactions, a durable retry queue or an automatic LCM installer.
