import { emptyState, formatTime, h, loader, tag } from "../dom.js";
import { parseBlocks } from "../text-blocks.js";

const LAYER_LABELS = {
  constitution: "团队规范",
  specs: "规格",
  work: "团队任务",
  members: "成员进度",
  activity: "活动",
};

const NARROW = "(max-width: 860px)";

// Paths, not document titles, define the explorer. Map keys also preserve literal
// names such as "__proto__" without treating them as object properties.
export function directoryEntries(files, prefix) {
  const root = { folders: new Map(), files: [] };
  for (const file of files) {
    const parts = file.path.slice(prefix.length + 1).split("/");
    const name = parts.pop();
    let parent = root;
    for (const part of parts) {
      if (!parent.folders.has(part)) parent.folders.set(part, { folders: new Map(), files: [] });
      parent = parent.folders.get(part);
    }
    parent.files.push({ ...file, name });
  }
  return root;
}

/** Render stored text as inert nodes. Document text is only ever assigned through textContent. */
function renderDocument(document) {
  const blocks = document.path.endsWith(".json") ? [{ type: "code", text: document.content }] : parseBlocks(document.content);
  return blocks.map((block) => {
    if (block.type === "heading") return h(`h${Math.min(block.level + 1, 6)}`, null, block.text);
    if (block.type === "code") return h("pre", { class: "code", tabindex: "0" }, block.text);
    if (block.type === "list") return h(block.ordered ? "ol" : "ul", null, block.items.map((item) => h("li", null, item)));
    return h("p", null, block.text);
  });
}

export function logView(ctx, workspace, route) {
  const { api } = ctx;
  const logHref = (path) => `#/w/${encodeURIComponent(workspace.id)}/log?path=${encodeURIComponent(path)}`;
  let currentPath = route.path ?? null;
  let fileCount = 0;
  let disposed = false;
  let readerRun = 0;
  const folders = new Map();

  const treeBody = h("div", { class: "tree-body" });
  const tree = h("details", { class: "tree" }, h("summary", { class: "explorer-heading" }, "工程文件"), treeBody);
  const reader = h("section", { class: "reader", "aria-label": "文件正文", tabindex: "-1" });

  // Start expanded on wide screens; narrow screens collapse once a file is open.
  const narrow = window.matchMedia(NARROW);
  const syncTree = () => { tree.open = !narrow.matches || !currentPath; };
  narrow.addEventListener("change", syncTree);
  treeBody.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-path]");
    // Selecting the already-open file has no hashchange, but must still return
    // a narrow-screen reader to its content and move focus out of the directory.
    if (link?.dataset.path === currentPath && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) {
      event.preventDefault();
      showCurrent(true);
    }
  });

  function markCurrent(reveal = false) {
    for (const link of treeBody.querySelectorAll("a")) {
      if (link.dataset.path === currentPath) {
        link.setAttribute("aria-current", "page");
        if (reveal) {
          for (const [path, folder] of folders) {
            if (currentPath.startsWith(`${path}/`)) folder.open = true;
          }
        }
      }
      else link.removeAttribute("aria-current");
    }
  }

  function folderNode(name, path, entries, description) {
    const summary = h("summary", { class: "folder-name", title: description ? `${name} · ${description}` : name }, name);
    const folder = h("details", { class: "folder", "data-folder": path, open: path.indexOf("/") === -1 }, summary,
      renderEntries(entries, path));
    folders.set(path, folder);
    return h("li", null, folder);
  }

  function renderEntries(entries, prefix) {
    const directories = [...entries.folders].sort(([a], [b]) => a.localeCompare(b));
    const files = [...entries.files].sort((a, b) => a.name.localeCompare(b.name));
    return h("ul", { class: "directory-list" },
      directories.map(([name, children]) => folderNode(name, `${prefix}/${name}`, children)),
      files.map((file) => h("li", null,
        h("a", { class: "file-name", href: logHref(file.path), "data-path": file.path, title: file.path }, file.name))),
      !directories.length && !files.length ? h("li", { class: "directory-empty" }, "空文件夹") : null);
  }

  const loadTree = loader(treeBody, () => api.getLogTree(workspace.id), (box, data) => {
    if (disposed) return;
    folders.clear();
    fileCount = data.categories.reduce((sum, category) => sum + category.files.length, 0);
    box.append(h("nav", { "aria-label": "工程日志目录" },
      h("ul", { class: "directory-root" }, data.categories.map((category) =>
        folderNode(category.key, category.key, directoryEntries(category.files, category.key), LAYER_LABELS[category.key])))));
    markCurrent(true);
    if (!currentPath) showPrompt();
  });

  function showPrompt() {
    reader.replaceChildren(fileCount
      ? emptyState("从目录中选择一个文件。", "工程日志只读；内容由成员在 OpenCode 中写入并同步。")
      : emptyState("这个空间还没有工程日志。", "成员在 OpenCode 中连接后，写入的规范、规格和进度会出现在这里。"));
  }

  function showCurrent(moveFocus) {
    const run = ++readerRun;
    syncTree();
    markCurrent(true);
    if (!currentPath) return showPrompt();
    const path = currentPath;
    // A changed address gets its own content target. An older read/retry may
    // finish, but it cannot replace the new document or steal its focus.
    const content = h("div", { class: "reader-content" });
    reader.replaceChildren(content);
    const done = loader(content, () => api.getLogDocument(workspace.id, path), (box, document) => {
      box.append(
        h("header", { class: "reader-head" },
          h("p", { class: "path" }, document.path),
          h("div", { class: "reader-meta" }, tag("只读"), h("span", null, `第 ${document.version} 版`),
            h("span", null, `${document.updatedByName} 更新于 ${formatTime(document.updatedAt)}`))),
        h("article", { class: "doc" }, renderDocument(document)));
    }, {
      renderError: (error) => (error.code === "not_found"
        ? emptyState("这个文件不存在，或已经被删除。", "请从目录中选择其他文件。") : null),
    })();
    if (moveFocus) done.then(() => { if (!disposed && run === readerRun) reader.focus(); });
    return done;
  }

  return {
    el: h("div", { class: "log-grid" }, h("aside", { class: "tree-panel", "aria-label": "文件浏览器" }, tree), reader),
    start() {
      loadTree();
      if (currentPath) showCurrent(false);
      else {
        syncTree();
        reader.replaceChildren(h("p", { class: "loading", role: "status" }, "正在加载…")); // The prompt depends on the tree.
      }
    },
    /** Same workspace and tab, different file: swap the document without rebuilding the page. */
    update(next) {
      currentPath = next.path ?? null;
      showCurrent(true);
    },
    dispose() {
      disposed = true;
      narrow.removeEventListener("change", syncTree);
    },
  };
}
