---
name: b-multi-role-ux-audit
description: "Audit a running web application through real browser workflows for multiple user roles, separately reporting correctness defects and user-experience friction."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Multi-Role UX Audit

## Preconditions

Confirm the application URL, roles, authenticated test accounts, scope, environment safety, and permitted writes before testing. Never assume a running service is disposable or use real credentials in a report. This audit is explicit-request only: never start it from a vague request.

## Audit Method

1. Define one representative workflow and page/feature coverage list for each role.
2. Test through a real browser, not code reading alone. The main Agent performs the walkthroughs itself; it does not delegate them to other agents.
3. For each role, assess two separate axes:
   - **correctness**: defects, logic gaps, incorrect state, access-control failures, and wrong data;
   - **experience**: confusion, excessive work, poor feedback, broken mental models, repeat-use fatigue, and counter-intuitive flows.
4. Cross-check symptoms across roles and APIs to find root causes, without calling API-only checks a UX test.
5. Clean up allowed test data and record any residue.

## Report

Separate findings into:

- correctness: severity, location, reproduction, expected, actual, impact, evidence;
- experience: frequency × pain, role, user impact, why the flow is unfriendly, suggested improvement.

State browser-tested, API-only, and untested coverage honestly. When the app is an active project, the report is the deliverable; record only durable outcomes (a confirmed defect class, an accepted limitation) in `.vibe/progress.md`, and open a Task only for a repair that needs persistent tracking.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
