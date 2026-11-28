import { readFileSync } from "node:fs";

export interface TemplateFile { path: string; content: string }
export interface TemplatePack { type: string; version: number; files: TemplateFile[] }

export const TYPE = "engineering-dev";
export const VERSION = 3;

const BEGIN = "<!-- VIBE-PROJECT-GENERAL:BEGIN -->";
const END = "<!-- VIBE-PROJECT-GENERAL:END -->";

// Generic rules are the authoritative "engineering-dev" template source. Local packages no longer carry a copy.
const rules = readFileSync(new URL("./general-rules.md", import.meta.url), "utf8").replace(/\r\n/g, "\n").trim() + "\n";

const agents = `${BEGIN}\n${rules}${END}\n\n## 项目级规则\n\n（暂无，可在此补充项目级规则。）\n`;

const progress = `# Project Progress

## Current stage

Not yet established.

## Completed milestones

None recorded.

## Durable decisions

None recorded.

## Known limitations

None recorded.

## Important remaining work

Not yet established.

<!-- Maintain current facts, not an append-only diary. Update only on durable changes; distinguish verified and unverified behavior, link relevant authoritative records, reconcile stale summaries. -->
`;

const requirements = `# Requirements Index

| id | title | status | version | tasks |
|---|---|---|---|---|

<!-- 每次创建 / 激活 / 取代基线时同步更新本表。 -->
`;

const lessons = `# Lessons Index

| id | 类型 | 状态 | 关键词 | 摘要 |
|---|---|---|---|---|

<!-- 每条经验独立成文件；先查索引再写，合并同类机制并维护状态、关键词与摘要。记录触发条件、证据和预防方法，不把未确认原因写成事实。 -->
`;

export const engineeringDev: TemplatePack = {
  type: TYPE,
  version: VERSION,
  files: [
    { path: "AGENTS.md", content: agents },
    { path: ".vibe/progress.md", content: progress },
    { path: ".vibe/docs/.gitkeep", content: "" },
    { path: ".vibe/requirements/README.md", content: requirements },
    { path: ".vibe/tasks/.gitkeep", content: "" },
    { path: ".vibe/lessons/README.md", content: lessons },
  ],
};
