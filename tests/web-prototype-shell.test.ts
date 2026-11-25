import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { request } from "node:http";
import type { AddressInfo } from "node:net";
import { join, relative, resolve } from "node:path";
import test from "node:test";

import { parseRoute } from "../web/js/router.js";
import { parseBlocks } from "../web/js/text-blocks.js";
import { CONTENT_SECURITY_POLICY, createWebServer } from "../web/serve.mjs";

const webRoot = resolve(import.meta.dirname, "../web");

function sourceFiles(directory = webRoot): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? sourceFiles(path) : [relative(webRoot, path).split("\\").join("/")];
  }).sort();
}
const read = (file: string) => readFileSync(join(webRoot, file), "utf8");

test("log text is classified into inert blocks and never turned into markup", () => {
  const blocks = parseBlocks([
    "# 标题", "", "第一行", "第二行", "", "- 甲", "* 乙", "1. 丙", "2) 丁", "",
    "```json", "{ \"a\": \"<b>\" }", "# 不是标题", "```",
    "<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "##### 五个井号不是标题",
  ].join("\r\n"));
  assert.deepEqual(blocks, [
    { type: "heading", level: 1, text: "标题" },
    { type: "paragraph", text: "第一行\n第二行" },
    { type: "list", ordered: false, items: ["甲", "乙"] },
    { type: "list", ordered: true, items: ["丙", "丁"] },
    { type: "code", text: "{ \"a\": \"<b>\" }\n# 不是标题" },
    { type: "paragraph", text: "<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n##### 五个井号不是标题" },
  ]);
  assert.deepEqual(parseBlocks(""), []);
  assert.deepEqual(parseBlocks("```\n未闭合的代码块"), [{ type: "code", text: "未闭合的代码块" }]);
});

test("hash routes resolve to pages, and anything else is unknown", () => {
  assert.deepEqual(parseRoute(""), { name: "root" });
  assert.deepEqual(parseRoute("#/login"), { name: "login" });
  assert.deepEqual(parseRoute("#/workspaces"), { name: "workspaces" });
  assert.deepEqual(parseRoute("#/invitations/ws_demo_pay"), { name: "invitation", workspaceId: "ws_demo_pay" });
  assert.deepEqual(parseRoute("#/w/ws_demo_pay"), { name: "workspace", workspaceId: "ws_demo_pay", tab: "overview", path: null });
  assert.deepEqual(parseRoute("#/w/ws_demo_pay/members"), { name: "workspace", workspaceId: "ws_demo_pay", tab: "members", path: null });
  assert.deepEqual(parseRoute(`#/w/ws_demo_pay/log?path=${encodeURIComponent("specs/modules/refund.md")}`),
    { name: "workspace", workspaceId: "ws_demo_pay", tab: "log", path: "specs/modules/refund.md" });
  for (const hash of ["#/w/ws_demo_pay/tasks", "#/w/ws_demo_pay/overview/extra", "#/nope", "#/w/%E0%A4%A/overview", "#/workspaces/x"]) {
    assert.deepEqual(parseRoute(hash), { name: "unknown" }, hash);
  }
});

test("the static server serves only the prototype files and forbids network connections", async (t) => {
  const server = createWebServer();
  await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  t.after(() => new Promise((done) => server.close(done)));
  const { port } = server.address() as AddressInfo;

  // Raw request paths: a client library would normalize "../" away before sending.
  const get = (path: string, method = "GET") => new Promise<{ status: number; headers: Record<string, any>; body: string }>((done, fail) => {
    const req = request({ host: "127.0.0.1", port, path, method }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => done({ status: res.statusCode!, headers: res.headers, body }));
    });
    req.on("error", fail);
    req.end();
  });

  const index = await get("/");
  assert.equal(index.status, 200);
  assert.match(index.headers["content-type"], /^text\/html/);
  assert.equal(index.body, read("index.html"));
  assert.equal(index.headers["content-security-policy"], CONTENT_SECURITY_POLICY);
  assert.equal(index.headers["cache-control"], "no-store");
  assert.equal(index.headers["x-content-type-options"], "nosniff");
  for (const rule of ["default-src 'none'", "connect-src 'none'", "script-src 'self'", "form-action 'none'"]) {
    assert.ok(CONTENT_SECURITY_POLICY.includes(rule), rule);
    assert.ok(read("index.html").includes(rule), `index.html meta policy: ${rule}`);
  }
  assert.doesNotMatch(CONTENT_SECURITY_POLICY, /unsafe-inline|unsafe-eval|https?:|\*/);

  for (const file of sourceFiles().filter((name) => /\.(js|css|svg)$/.test(name))) {
    const reply = await get(`/${file}`);
    assert.equal(reply.status, 200, file);
    assert.equal(reply.body, read(file), file);
  }
  assert.match((await get("/js/main.js")).headers["content-type"], /^text\/javascript/);
  assert.equal((await get("/index.html?x=1", "HEAD")).body, "");

  for (const path of [
    "/serve.mjs", "/README.md", "/missing.js", "/js/", "/js/missing.js",
    "/../package.json", "/js/../../package.json", "/..%2fpackage.json", "/js/..%2f..%2fserver/main.ts",
    "/%2e%2e/%2e%2e/etc/passwd", "/js%5cmain.js", "/%E0%A4%A", "/js/main.js%00.html",
  ]) {
    assert.equal((await get(path)).status, 404, path);
  }
  const post = await get("/", "POST");
  assert.equal(post.status, 405);
  assert.equal(post.headers.allow, "GET, HEAD");
});

test("prototype sources load nothing remote and never build markup from strings", () => {
  const files = sourceFiles();
  assert.deepEqual(files.filter((file) => !file.startsWith("js/")), ["README.md", "favicon.svg", "index.html", "serve.mjs", "styles.css"]);
  const scripts = files.filter((file) => file.endsWith(".js"));
  assert.ok(scripts.length >= 10);

  const forbidden = /\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts|innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|\bimport\s*\(|sessionStorage|document\.cookie|indexedDB/;
  for (const file of scripts) assert.doesNotMatch(read(file), forbidden, file);

  // Every address written in the sources is synthetic, apart from the SVG namespace identifier.
  for (const file of [...scripts, "index.html", "styles.css", "favicon.svg"]) {
    for (const [url, host] of read(file).matchAll(/\b(?:https?|wss?|ftp):\/\/([^\s/"'`<>)]+)/g)) {
      assert.ok(host === "www.w3.org" || host === "<工作台地址>" || /(^|\.)example\.test$/.test(host), `${file}: ${url}`);
    }
  }
  const html = read("index.html");
  for (const [, target] of html.matchAll(/\b(?:src|href)="([^"]*)"/g)) assert.match(target, /^\.\/[\w./-]+$/, target);
  assert.doesNotMatch(html, /<script(?![^>]*\bsrc=)|\son\w+=|style=/i, "no inline script, handler or style");
  assert.doesNotMatch(read("styles.css"), /@import|url\(/);
  assert.doesNotMatch(read("favicon.svg"), /<script|href|\son\w+=/i);
});

test("pages reach data only through the injected interface", () => {
  const scripts = sourceFiles().filter((file) => file.endsWith(".js"));
  for (const file of scripts.filter((name) => name !== "js/main.js")) {
    assert.doesNotMatch(read(file), /localStorage/, `${file}: only the entry point picks the storage`);
  }
  for (const file of scripts.filter((name) => name.startsWith("js/views/") || name === "js/dom.js")) {
    assert.doesNotMatch(read(file), /mock-api\.js|seed\.js/, `${file}: pages must not import the mock or its fixtures`);
  }
  assert.match(read("js/main.js"), /createMockApi\(\{ storage: browserStorage\(\) \}\)/);
  // The seed is pure data plus one factory: it must not touch storage, time or the DOM by itself.
  assert.doesNotMatch(read("js/seed.js"), /Date\.now|document\.|window\./);
});
