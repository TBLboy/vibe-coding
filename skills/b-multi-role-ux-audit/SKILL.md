---
name: b-multi-role-ux-audit
description: Audit a running web application through real browser workflows for multiple user roles, separately reporting correctness defects and user-experience friction.
license: MIT
compatibility: codex
metadata:
  type: web-application-audit-skill-pack
  output: prioritized-role-audit-report
---

# Multi-Role UX Audit

## Preconditions

Confirm the application URL, roles, authenticated test accounts, scope, environment safety, and permitted writes before testing. Never assume a running service is disposable or use real credentials in a report.

## Audit Method

1. Define one representative workflow and page/feature coverage list for each role.
2. Test through a real browser, not code reading alone. Delegate independent role walkthroughs only when credentials and non-destructive boundaries are known.
3. For each role, assess two separate axes:
   - **correctness**: defects, logic gaps, incorrect state, access-control failures, and wrong data;
   - **experience**: confusion, excessive work, poor feedback, broken mental models, repeat-use fatigue, and counter-intuitive flows.
4. Cross-check symptoms across roles and APIs to find root causes, without calling API-only checks a UX test.
5. Clean up allowed test data and record any residue.

## Report

Separate findings into:

- correctness: severity, location, reproduction, expected, actual, impact, evidence;
- experience: frequency × pain, role, user impact, why the flow is unfriendly, suggested improvement.

State browser-tested, API-only, and untested coverage honestly. Save findings in `.project-log/alignment/findings.yaml` or linked audit evidence when the app is an active project.
