# Curated UI design sources

This file records the public material used by `b-ui-design`. Active secondary
routes are the self-contained adaptations in `guides/`, not upstream workflows.
The `sources/` snapshots are provenance-only: read them as source material, never
as executable plugins, installers, hooks, or independent Skills. They retain
historical commands and links to unbundled files; none is an active dependency.

Snapshot date: 2026-11-24

| Snapshot directory | Upstream repository | Commit | License | Selected scope |
|---|---|---|---|---|
| `sources/interface-design/` | [Dammyjay93/interface-design](https://github.com/Dammyjay93/interface-design) | `2f9be3206855bcb2d1d0af262c8bae25cba6658d` | MIT; local copy in `LICENSE` | Product UI direction, hierarchy, density, tokens, consistency |
| `sources/impeccable/` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `b49177d32788f2dc585c42831d845dacf1ebed2c` | Apache-2.0; local copy in `LICENSE`, notice in `NOTICE.md` | Surface modes, critique, audit, operate/read guidance and craft floor |
| `sources/frontend-design/` | [anthropics/skills](https://github.com/anthropics/skills) (`skills/frontend-design`) | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` | Apache-2.0; local copy in `LICENSE.txt` | New visual direction, typography, layout, anti-template review |
| `sources/emil/` | [emilkowalski/skills](https://github.com/emilkowalski/skills) | `64eb3deb9a5fbfa041faf783e0bc3fd635872e9c` | MIT; local copy in `LICENSE` | Component polish, motion decisions, mobile Web, worst-case data |
| `sources/ui-ux-pro-max/` | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `f2f7266b07805025421611656045e9b44b41e2eb` | MIT; local copy in `LICENSE` | Scenario/style guidance, UX guidelines, responsive and pre-delivery references |

## Why these sources

- `interface-design` owns operational product-interface structure.
- `impeccable` owns critique and surface-mode distinctions for existing UI.
- `frontend-design` contributes visual-direction discipline for new surfaces.
- `emil` contributes narrow, specialist checks rather than page-level authority.
- `ui-ux-pro-max` informs bounded scenario comparison without becoming the final decision maker. Its dataset/search engine is not shipped; there is no offline searchable catalog in this package.

## Adaptation and attribution

The original router is MIT. Adapted guides retain their source terms: product UI
combines MIT Interface Design with Apache-2.0 Impeccable; marketing, reading and
critique guides derive from Apache-2.0 sources; interaction, mobile, resilience
and scenario guides derive from MIT sources. Do not apply the router's MIT label
to the whole mixed-license bundle. Keep source licenses/notices when redistributing.

Adapted 2026-11-24 for Vibe Coding V2: replaced tool-specific setup, independent
memory files, mandatory scripts, hooks and delegation with self-contained methods
under the existing V2 lifecycle; softened absolute style preferences into contextual
choices; preserved project constraints and permission boundaries. The resilience
guide includes its own case catalog. The scenario guide explicitly limits coverage
without the upstream search engine. These are changed adaptations, not unmodified
official upstream Skills or endorsements.

The current bundle intentionally does not include the full Taste Skill because its primary rules target company/marketing sites and asset-heavy visual pages. It remains a future candidate for an explicitly approved marketing-surface route, not a default product-UI dependency.

## Integrity and redistribution notes

- Each selected source keeps its upstream license file beside the copied material.
- `sources.lock.json` records each file's original path, repository URL, exact
  commit and normalized SHA-256. `upstream.md` is the original upstream SKILL.md
  renamed to avoid nested Skill discovery; its content is unchanged.
- Only the selected text references are copied; source CLIs, hooks, binaries, scripts, data catalogs, remote assets, and plugin configuration are not copied.
- Future updates require a new review of source content, license, commit, and routing impact. Do not silently replace a pinned snapshot.
