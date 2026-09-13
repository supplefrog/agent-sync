# Adversarial persona mode

Use only when a skeptical or constrained user perspective could expose adoption friction that ordinary functional QA misses.

## 1. Define a credible persona

Derive the persona from the product’s actual audience and task. Specify:

- the job they need to complete;
- relevant constraints such as low patience, low technical familiarity, motor/vision limitations, distrust, time pressure, or an established alternative workflow;
- what would make them abandon the task;
- what success looks like.

Avoid age, disability, occupation, or cultural stereotypes. The persona should alter test behavior, not merely add entertaining dialogue.

## 2. Test the core task in character

Attempt the persona’s job from cold start. Record friction around terminology, navigation, onboarding, readability, interaction cost, feedback, errors, recovery, trust, and whether the app improves on their current method. Capture observable evidence under the parent dogfood workflow.

A short in-character reaction may make the experience vivid, but do not let performance replace reproduction evidence.

## 3. Return to neutral triage

Classify every complaint:

- **Real defect:** reproducible failure or accessibility/usability problem likely to affect intended users.
- **Valid limited-audience friction:** real but bounded to the specified constraint.
- **Product opportunity:** useful improvement revealed by the test, not a defect.
- **Persona noise:** preference, resistance, or unsupported reaction with no product evidence.

Only the first three belong in the actionable assessment, clearly labeled. Never publish raw persona complaints as tickets.

## 4. Report

Include the persona and task, whether they completed it, abandonment points, evidence-backed findings, limited-audience caveats, and discarded persona noise. Create external tickets only when the user explicitly requests publication.
