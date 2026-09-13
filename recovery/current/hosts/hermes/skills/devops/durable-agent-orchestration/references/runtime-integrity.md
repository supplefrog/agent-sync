# Persisted runtime integrity

1. Normalize the plan, snapshot the route catalog and exact selector bytes, and bind their hashes in host-owned immutable run evidence.
2. Verify once at the host boundary and carry the trusted digest or verified bytes through every later state mutation; never verify one read and execute another.
3. Serialize lifecycle mutations. Persist claim, native handle, and unique attempt token before accepting completion.
4. Give every physical attempt a unique output path. Store close evidence outside worker-writable state and verify the handle plus descendants are inactive before retry.
5. Contain artifact paths, reject link/reparse escapes and Unicode line separators in single-line handles, and use exclusive same-directory temporary files followed by flush/fsync and atomic replace.
6. On cancellation, await every child, persist terminal transitions, scan exact argv/handles for survivors, reconcile run-owned sessions, and only then permit relaunch.
7. Preserve the original physical-attempt cap and raw evidence hashes; overlapping writers, unknown liveness, stale tokens, or missing receipts invalidate acceptance.

A wrapper exit or missing parent is never sufficient process-tree evidence. On Windows terminate only the exact recorded tree after required approval, then repeat the exact-argv scan and require zero matches.
