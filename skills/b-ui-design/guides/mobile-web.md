# Mobile Web — platform behavior

Adapted from Emil Kowalski's Mobile Native (MIT), pinned in `../SOURCES.md`.
This is mobile Web guidance, not a native iOS/Android implementation workflow.

## Capability, not device guesses

Inspect the actual task and existing platform behavior. Touch and mouse coexist:
use pointer/hover capabilities rather than user-agent sniffing or assuming width
means touch. Prefer CSS/platform mechanisms over a new JavaScript device layer.
Apply fixes only where the problem exists; a native-feeling interface still needs
selectable prose, browser navigation and accessible controls.

## Layout, input and scrolling

Check viewport sizing with browser chrome open/closed, virtual keyboard, dynamic
viewport units and safe-area insets where supported. A desktop 100vh composition
may hide bottom actions on a real phone. Keep primary actions reachable without
covering content or focused fields. Sticky/fixed regions require actual overlap
checks, not just z-index changes.

Never disable pinch zoom to prevent input auto-zoom. Inspect input font sizes,
labels, keyboard types and real-device focus behavior instead. Keep touch targets
comfortable and separated; do not shrink them to force the desktop composition
onto a phone. Reflow content priority, not merely column count.

Gate hover-only styling on suitable capabilities. Preserve visible focus and
press feedback. Diagnose tap highlights, text selection and gesture interference
locally: globally disabling selection or touch behavior can break reading and
browser zoom. Do not suppress scrolling/pull-to-refresh without a concrete need.

## Evidence and boundaries

Inspect narrow and medium widths plus long content, enlarged text, landscape and
keyboard-open states where tools allow. Check nested scroll areas and the first/
last content beneath sticky bars. Browser emulation proves responsive geometry,
not native touch behavior, keyboard timing, rubber-banding or safe-area correctness.
List which checks require hardware and do not claim a true phone pass from a
desktop screenshot. Do not expose a loopback server to a network or change binding
policy merely to obtain a device test without authorization.
