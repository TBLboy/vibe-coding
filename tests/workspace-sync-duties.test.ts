import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const read = (p: string): string => readFileSync(new URL('../' + p, import.meta.url), 'utf8').replace(/\r\n/g, '\n');

test('vibe-main carries the connect route and the three sync duties, kept short', () => {
  const main = read('runtime/opencode/agents/vibe-main.md');
  const row = main.split('\n').find((l) => l.includes('`a-workspace-connect`'));
  assert.ok(row, 'routing row present');
  assert.match(row!, /连接工作空间/);
  const section = main.split('## 工作空间同步职责')[1];
  assert.ok(section, 'sync duties section present');
  assert.match(section, /a-workspace-connect/);
  assert.match(section, /workspace_resolve_conflict/);
  assert.match(section, /只提示一次/);
  assert.match(section, /不要自行取舍/);
  assert.ok(section.trim().split('\n').filter((l) => l.trim()).length <= 6, 'at most 6 lines');
});

test('a-workspace-connect skill is registered and never persists or echoes the Key', () => {
  const skill = read('skills/a-workspace-connect/SKILL.md');
  assert.match(skill, /^---\nname: a-workspace-connect\n/);
  assert.match(skill, /Do not write it into any file/);
  assert.doesNotMatch(skill, /TEAM_TASK_KEY|TEAM_SESSION_TOKEN|workspace token|TEAM_SERVER_URL/);
});

test('the tool surface is exactly the five workspace tools', () => {
  const tools = read('runtime/opencode/plugins/vibe-v2/team/tools.ts');
  const names = [...tools.matchAll(/name: '(workspace_[a-z_]+)'/g)].map((m) => m[1]).sort();
  assert.deepEqual(names, ['workspace_connect', 'workspace_disconnect', 'workspace_resolve_conflict', 'workspace_status', 'workspace_sync']);
});
