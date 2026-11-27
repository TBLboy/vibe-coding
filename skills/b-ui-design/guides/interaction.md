# Interaction craft — components and motion

Adapted from Emil Kowalski's Design Engineering (MIT), pinned in `../SOURCES.md`.
This guide is framework-neutral and does not require Motion or any UI library.

## Capability and feedback before animation

For the specific component define trigger, allowed action, resulting state,
feedback, cancellation/retry and focus destination. Use native semantics and
existing primitives; appearance must match capability. Static metadata must not
look like a button; a disabled control needs an understandable reason.

Cover relevant default, hover, focus, pressed, busy, disabled, success, error and
empty states. Prevent duplicate submissions, preserve recoverable input and never
announce success before completion. Keep dimensions stable as labels or counts
change. Errors should explain what happened and what the user can do next.

## Decide whether to move

Ask how often the user sees the interaction and whether movement explains a
relationship, state change or feedback. Frequent keyboard actions should not wait
through decorative movement. Sometimes the right polish is removing animation.
Do not make every component bounce or every section fade in.

When motion is useful, use immediate response and restrained duration matched to
the component; small feedback often needs roughly 100–200ms, not a universal timer.
Entering UI commonly benefits from responsive ease-out; constant progress and
on-screen movement have different needs. Popovers should feel connected to their
trigger. Avoid dramatic scale-from-zero entrances. Small press feedback is optional,
not a command to transform every button or dense text control.

Keep transitions bounded to intended properties. Prefer compositor-friendly motion
where appropriate and respect reduced motion without hiding state. Make interrupted
open/close actions settle in the correct final state; do not trade semantic or
focus correctness for visual continuity. Springs are an option for direct
manipulation, not permission to add a library.

## Evidence

Check keyboard and pointer interaction, focus visibility/return, rapid repeated
actions, pending completion, failure/retry and reduced-motion behavior. Test
touch-specific behavior only when relevant; hover effects should not become sticky
on coarse pointers. Inspect the actual interaction over time rather than approving
motion from a still screenshot. State when real-device or performance measurement
is unavailable.
