# Defect acceptance before taste review

Use this for interactive, responsive or motion-bearing changes. Keep the record in the project's existing requirements, test or handoff artifact. A simple repair needs only its affected cases; a whole-page build needs the user journeys and their responsive transformations. Use the project's mature tests and accessible primitives before adding machinery.

## Choose cases before composing controls

Start from what the person must accomplish, where they will be when doing it, and how they enter, exit or recover. For each affected job, identify its access path, meaningful feedback and the relevant input/layout contexts. This exposes duplicate navigation and unreachable actions before they become widgets. Different access paths can be useful when their contexts differ; do not remove them solely because they share a destination.

Record the important behavior promises as observable relationships, with the scenario and an appropriate tolerance: a trigger stays anchored while its disclosure opens; a reading action is usable at the reading position; each valid activation produces the intended state; a panel finishes without an unplanned geometry jump. Intentional movement, deferred actions and responsive rearrangement need their own expectations. Do not turn these examples into universal layout rules.

Choose representative content and stress cases capable of falsifying those promises. Include the actual long list or answer, the relevant phone layout, and scrollbar occupancy when these affect the changed behavior. A tiny demonstration cannot establish acceptance of the full-content surface. Freeze expected behavior before collecting results; do not weaken it to make a failed implementation pass. Change an expectation only for a documented brief or design reason, then rerun affected cases.

## Collect evidence from the experience

Exercise the complete task with ordinary supported input. Check the surrounding page as well as the isolated component. For state changes, observe trigger, content, neighboring layout and destination through entry, exit, interruption/reversal and final settlement, plus relevant keyboard, touch and reduced-motion paths. Inspect motion at normal speed and inspect intermediate frames when needed to locate a defect. Separate control rotation from movement of its entire container. Include the actual reading or use position; locator auto-scrolling can conceal an inaccessible action.

Bind observations to the build/revision or file hash, browser, viewport, content fixture, starting state, input and capture method. Retain raw geometry/event records or recordings behind the finding. Measure browser facts rather than asking a model to guess coordinates, hit targets or capture completeness. Keep unsupported checks unresolved and distinguish emulation from physical-device evidence.

For repeated measurable checks, execute [../scripts/frontend_gate.py](../scripts/frontend_gate.py) using a project-local contract and collected observations. See [defect-gate-schema.md](defect-gate-schema.md) for the four supported checks, collector requirements, examples and exit codes. Use only applicable promises. The checker verifies supplied measurements; it does not inspect the browser, prove coverage, certify accessibility or judge design. An excluded promise or passing fixture is not evidence that a task was tested.

## Review findings and accept

Classify findings by their evidence:

- **Defect:** a task, accessibility requirement or declared behavior fails; a visual explanation contradicts the state or relationship it is meant to convey. Reproduce it and fix the cause.
- **Taste:** several coherent, usable treatments meet the brief. Offer a scoped comparison when the choice is material and unresolved.
- **Unresolved:** intent, observation or coverage is insufficient to decide. Obtain the missing evidence or clarify the particular decision; do not silently count it as passed.

Interpret visual conventions in context. An upward caret can mean collapse while a list opens below; abstract theme motion need not imitate sunlight. When an effect deliberately depicts a source, direction or attachment, inspect whether the rendered sequence consistently conveys that relationship. A metaphor disagreement without an observable contradiction remains a taste or unresolved question.

For a consequential composition or interaction whose task/coherence review benefits from separate inspection, use a fresh reviewer under the standing dispatch contract. Give the brief, artifact and selected cases before the author's explanation or verdict. Request additional task/coverage gaps, not only confirmation of supplied findings. The parent reproduces findings and accepts the result; a reviewer verdict is not evidence by itself. Small unambiguous repairs need no compulsory reviewer.

Fix known defects and retest their causes and affected neighbors. Missing material evidence blocks readiness just as a known failure does. Label exploratory demos accordingly; do not hand a failed result to the user as ready for taste review. Report the revision, observed scope, remaining gaps and whether defect acceptance passed. Preserve the skill's separate rendered delivery and user approval requirements before visual commits. Stop when the task and acceptance criteria are met; no fixed pass count or endless reviewer loop is required.
