# Optional UI variant prototype

Use this recipe when trying alternatives in the project's real UI will answer a visual or interaction question. A component comparison, separate previews, labelled screenshots or the user's existing comparison tool may be enough; do not force a variant route, option count or picker onto every frontend task. Follow [taste-selection.md](taste-selection.md) for selection and delivery, and [component-selection.md](component-selection.md) for external parts.

State the question and vary the dimension that answers it. Layout concepts need meaningfully different structure, hierarchy or affordances; a palette question may share structure. Share data and accessible primitives without making every concept inherit the same layout.

## Keep the real context without changing the product first

For an existing page or a new element that belongs inside one, reproduce its surrounding header, navigation, representative data and density in an isolated preview. Preserve the relevant route parameters, data flow and auth assumptions. When a scoped demo is required before product edits, use a preview copy, development-only route or isolated checkout; do not put provisional variants into the actual page before that review. Use a clearly marked standalone prototype route when there is no suitable host context, following the project's routing conventions.

Make the preview runnable through the project's existing command and expose the relevant state. Prefer memory or fixtures; use a clearly disposable store only when persistence is the question. Stub consequential mutations instead of pointing visual options at live writes. Label absent or untested behavior and perform the checks appropriate to what the preview demonstrates.

## Make each option easy to revisit

Give variants stable identifiers and shareable links, for example a `?variant=` parameter that survives reload. Use the framework's router without discarding unrelated query parameters or page state. Deliver the actual accessible URLs or representative captures to the user; a local URL is useful only where the user can reach it.

An optional development-only switcher can show the current option and cycle with labelled controls. If arrow-key shortcuts are used, do not intercept typing, editable controls or existing keyboard interactions. Keep the switcher visually separate from the evaluated design and exclude it from production. A floating bottom bar is one possible presentation, not a required design.

## Preserve the answer and retire the experiment

Record the selected or combined qualities, the question settled and useful preview/source links in the existing project context. Preserve useful primary-source variants recoverably before removing losing options and the switcher; a throwaway branch is appropriate when it fits the project's workflow. Use `breadcrumb-records` for substantial closeout when no equivalent record exists. Do not require a new issue or branch for every small comparison.

Integrate the selected treatment with production checks, accessibility, state handling and error paths. Prototype code's reduced scope does not establish production readiness. Remove prototype routes and controls from the shipped surface.

Provenance: adapted from the locally installed Emil Kowalski `prototype` skill's `UI.md`, already referenced by [component-selection.md](component-selection.md#existing-foundations), under its [MIT license notice](prototype-LICENSE.txt). The former fixed counts, mandatory floating picker and universal branch/issue capture are optional here; their useful comparison, isolation, stable-link and recovery mechanisms remain.
