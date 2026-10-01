# Acceptance boundary controls

For parallel-result acceptance, make boundary stubs produce distinct outputs from actual child inputs, reorder only returned results and verify persisted identity-to-output mappings. Rewriting summaries after execution can hide crossed inputs.

For durable acceptance gates, pair each disqualifying result with an otherwise identical eligible control, reload state and check dependent readiness before and after explicit acceptance. Rejection-only checks can pass when every result is rejected.

For a supplied verification script, inspect its assertions, require nonzero exit on acceptance failure, exercise a failing control and rerun after repair. A successful process can conceal violations merely printed as JSON. Bind the result to the tested revision.
