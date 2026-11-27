import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { connectWorkspace } from "./binding.ts";

// Local connector: credentials come from the environment only, never from arguments or tool input.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { WORKBENCH_URL: serverUrl, WORKBENCH_KEY: key } = process.env;
  if (!serverUrl || !key) {
    process.stderr.write("WORKBENCH_URL and WORKBENCH_KEY are required\n");
    process.exitCode = 1;
  } else {
    connectWorkspace(resolve(process.argv[2] ?? "."), { serverUrl, key })
      .then((result) => {
        process.stdout.write(result.status === "bound_to_other"
          ? "This directory is already bound to another workspace; disconnect it first.\n"
          : "Connected. Use /reload to load workspace tools.\n");
        if (result.status === "bound_to_other") process.exitCode = 1;
      })
      .catch(() => { process.stderr.write("Connection failed: verify the server URL and the workspace Key.\n"); process.exitCode = 1; });
  }
}
