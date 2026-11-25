// Loopback-only static server for the mock prototype. It serves the allowlisted
// files in this directory and nothing else; there is no API behind it.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = import.meta.dirname;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
};

// The page may load its own files and may not open any network connection.
export const CONTENT_SECURITY_POLICY =
  "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";

const HEADERS = {
  "Content-Security-Policy": CONTENT_SECURITY_POLICY,
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Cache-Control": "no-store",
};

function resolveFile(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  if (decoded.includes("\0") || decoded.includes("\\")) return null;
  const relative = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const file = resolve(ROOT, relative);
  if (!file.startsWith(ROOT + sep)) return null; // No path may leave this directory.
  const local = file.slice(ROOT.length + 1).split(sep).join("/");
  const allowed = local === "index.html" || local === "styles.css" || local === "favicon.svg" || /^js\/[\w./-]+\.js$/u.test(local);
  return allowed && TYPES[extname(file)] ? file : null;
}

export function createWebServer() {
  return createServer(async (request, response) => {
    const send = (status, type, body) => {
      response.writeHead(status, { ...HEADERS, "Content-Type": type });
      response.end(request.method === "HEAD" ? undefined : body);
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.setHeader("Allow", "GET, HEAD");
      return send(405, "text/plain; charset=utf-8", "Method not allowed\n");
    }
    const file = resolveFile(new URL(request.url ?? "/", "http://localhost").pathname);
    if (!file) return send(404, "text/plain; charset=utf-8", "Not found\n");
    try {
      return send(200, TYPES[extname(file)], await readFile(file));
    } catch {
      return send(404, "text/plain; charset=utf-8", "Not found\n");
    }
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.WEB_PORT ?? 7420);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    console.error("WEB_PORT must be an integer between 0 and 65535.");
    process.exit(1);
  }
  const server = createWebServer();
  server.on("error", (error) => {
    console.error(error.code === "EADDRINUSE" ? `Port ${port} is in use. Set WEB_PORT to another port.` : error.message);
    process.exit(1);
  });
  server.listen(port, "127.0.0.1", () => {
    console.log(`Team workspace web prototype (mock data only): http://127.0.0.1:${server.address().port}/`);
  });
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.close(() => process.exit(0)));
}
