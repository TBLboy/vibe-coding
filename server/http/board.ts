import type { Board } from "../domain/board.ts";

function escape(value:unknown): string {
  return String(value??"").replace(/[&<>"']/gu,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]!));
}
function shell(body:string): string {
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>团队看板</title><body><main>${body}</main></body></html>`;
}
export function boardForm(): string {
  return shell(`<h1>团队看板</h1><form method="post" action="/board"><p><label>工作空间 ID <input name="workspaceId" required></label></p><p><label>Workspace token <input type="password" name="token" autocomplete="off" required></label></p><button>查看</button></form><p>凭据仅通过请求正文提交，不会保存在网址或页面中。刷新时需重新提交。</p>`);
}
export function renderBoard(name:string,board:Board): string {
  const labels={open:"待领取",claimed:"进行中",done:"完成",abandoned:"放弃"};
  const columns=Object.entries(board.tasks).map(([status,tasks])=>`<section><h2>${labels[status as keyof typeof labels]}</h2><ul>${tasks.map(task=>`<li><strong>${escape(task.title)}</strong> (${escape(task.id)})<br>持有者：${escape(task.claimedBy??"—")}<br>更新时间：${escape(task.updatedAt)}<br>范围：${escape(task.scope.join(", "))}<br>原因：${escape(task.closedReason)}</li>`).join("")}</ul></section>`).join("");
  return shell(`<h1>${escape(name)}</h1><h2>成员</h2><ul>${board.members.map(member=>`<li>${escape(member.displayName)} (${escape(member.role)}) — ${member.online?"在线":"离线"}；最近在线 ${escape(member.lastSeenAt??"—")}；任务 ${escape(member.currentTaskId??"—")}</li>`).join("")}</ul>${columns}<h2>最近变更</h2><ol>${board.recentChanges.map(change=>`<li>#${escape(change.seq)} ${escape(change.path)} ${escape(change.op)} v${escape(change.version)} — ${escape(change.by)} ${escape(change.at)}</li>`).join("")}</ol>`);
}
