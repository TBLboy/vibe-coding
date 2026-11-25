// Small DOM helpers shared by the pages. Content is always written as text
// nodes or attributes; nothing in the prototype parses strings as HTML.

const SVG_NS = "http://www.w3.org/2000/svg";
const ICON_PATHS = {
  back: ["M15 6l-6 6 6 6"],
  copy: ["M9 9h10v11H9z", "M5 15V4h10"],
  folder: ["M3 7h7l2 2h9v10H3z"],
  file: ["M6 3h8l4 4v14H6z", "M14 3v4h4"],
  plus: ["M12 5v14", "M5 12h14"],
};

let idCounter = 0;
export const uid = (prefix) => `${prefix}-${++idCounter}`;

function append(parent, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    if (Array.isArray(child)) append(parent, child);
    else parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/** Create an element. `on*` function attributes become listeners; other values become attributes. */
export function h(tag, attributes, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes ?? {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name.startsWith("on") && typeof value === "function") element.addEventListener(name.slice(2), value);
    else if (name === "class") element.className = value;
    else element.setAttribute(name, value === true ? "" : String(value));
  }
  append(element, children);
  return element;
}

/** Decorative single-colour line icon. It never replaces the text label next to it. */
export function icon(name) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const data of ICON_PATHS[name]) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", data);
    svg.append(path);
  }
  return svg;
}

const two = (value) => String(value).padStart(2, "0");

/** "10:40" today, "昨天 10:40" yesterday, otherwise "11月22日 10:40". */
export function formatTime(timestamp, now = Date.now()) {
  if (timestamp === null || timestamp === undefined) return "暂无记录";
  const date = new Date(timestamp);
  const clock = `${two(date.getHours())}:${two(date.getMinutes())}`;
  const dayStart = (value) => new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  const days = Math.round((dayStart(new Date(now)) - dayStart(date)) / 86400000);
  if (days === 0) return clock;
  if (days === 1) return `昨天 ${clock}`;
  return `${date.getMonth() + 1}月${date.getDate()}日 ${clock}`;
}

export const ROLE_LABELS = { owner: "负责人", member: "成员" };

export function tag(text, kind = "neutral") {
  return h("span", { class: `tag tag-${kind}` }, text);
}

export function avatar(name, size) {
  return h("span", { class: size ? `avatar avatar-${size}` : "avatar", "aria-hidden": "true" }, [...String(name)][0] ?? "?");
}

export function emptyState(title, hint) {
  return h("div", { class: "empty" }, h("p", { class: "empty-title" }, title), hint ? h("p", { class: "empty-hint" }, hint) : null);
}

/** A failed read: short explanation plus a user-triggered retry. */
export function errorState(error, onRetry) {
  return h("div", { class: "notice notice-error", role: "alert" },
    h("p", { class: "notice-title" }, "加载失败"),
    h("p", null, `${error?.message ?? "发生了未知错误。"}数据没有变化，可以重试。`),
    h("button", { type: "button", class: "btn", onclick: onRetry }, "重试"));
}

/**
 * Load data into a container with loading and failure states. Returns `reload`.
 * `renderError(error, retry)` may return a node for errors that need their own page.
 */
export function loader(container, load, render, { renderError } = {}) {
  let latest = 0;
  async function reload() {
    const run = ++latest;
    container.replaceChildren(h("p", { class: "loading", role: "status" }, "正在加载…"));
    try {
      const data = await load();
      if (run !== latest) return;
      container.replaceChildren();
      render(container, data);
    } catch (error) {
      if (run !== latest) return;
      container.replaceChildren(renderError?.(error, reload) ?? errorState(error, reload));
    }
  }
  return reload;
}

let toastTimer = null;
/** Short asynchronous feedback, announced politely to assistive technology. */
export function notify(message, kind = "ok") {
  const toast = document.getElementById("toast");
  toast.className = `toast toast-${kind} toast-visible`;
  toast.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.className = "toast";
    toast.textContent = "";
  }, 6000);
}

/**
 * Run one submission. The button (and any related controls) stay disabled while
 * it is pending, so a second click cannot submit again.
 */
export async function runOnce(button, action, related = []) {
  if (button.dataset.busy) return undefined;
  const controls = [button, ...related];
  const label = button.querySelector(".btn-label") ?? button;
  const text = label.textContent;
  button.dataset.busy = "1";
  for (const control of controls) control.disabled = true;
  label.textContent = "处理中…";
  try {
    return await action();
  } finally {
    delete button.dataset.busy;
    label.textContent = text;
    for (const control of controls) control.disabled = false;
  }
}

/** A labelled input with a field-level error slot. */
export function field({ label, hint, ...attributes }) {
  const id = uid("field");
  const error = h("p", { class: "field-error", id: `${id}-error` });
  const hintNode = hint ? h("p", { class: "field-hint", id: `${id}-hint` }, hint) : null;
  const input = h("input", { class: "input", id, "aria-describedby": `${hint ? `${id}-hint ` : ""}${id}-error`, ...attributes });
  const row = h("div", { class: "field" }, h("label", { for: id }, label), input, hintNode, error);
  const setError = (message) => {
    error.textContent = message ?? "";
    if (message) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
  };
  return { row, input, setError };
}

/**
 * Show an API failure inside a form. Field errors go next to their inputs and
 * the first one receives focus; anything else goes to the form-level message.
 */
export function showFormError(error, fields, formMessage) {
  const problems = error?.code === "invalid" ? error.details?.fields ?? {} : {};
  let first = null;
  let unplaced = error?.code === "invalid" ? "" : error?.message ?? "发生了未知错误。";
  for (const [name, message] of Object.entries(problems)) {
    const target = fields[name];
    if (!target) {
      unplaced = message;
      continue;
    }
    target.setError(message);
    first ??= target;
  }
  formMessage.textContent = unplaced;
  first?.input.focus();
}

/** Modal dialog. Escape and the close button both return focus to the trigger. */
export function openDialog({ title, trigger, build }) {
  const titleId = uid("dialog-title");
  const body = h("div", { class: "dialog-body" });
  const dialog = h("dialog", { class: "dialog", "aria-labelledby": titleId },
    h("div", { class: "dialog-head" },
      h("h2", { id: titleId }, title),
      h("button", { type: "button", class: "btn btn-quiet", onclick: () => dialog.close() }, "关闭")),
    body);
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (trigger?.isConnected) trigger.focus();
    else document.querySelector("main h1")?.focus();
  });
  document.body.append(dialog);
  build(body, { close: () => dialog.close() });
  dialog.showModal();
  return dialog;
}

/** Copy example text. Reports honestly when the browser refuses clipboard access. */
export async function copyText(text, what) {
  try {
    await navigator.clipboard.writeText(text);
    notify(`已复制${what}。`);
  } catch {
    notify(`无法自动复制，请手动选中${what}后复制。`, "error");
  }
}

export function copyButton(text, what) {
  return h("button", { type: "button", class: "btn btn-small", onclick: () => copyText(text, what) },
    icon("copy"), h("span", { class: "btn-label" }, `复制${what}`));
}
