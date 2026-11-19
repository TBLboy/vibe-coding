import { Plugin } from "@opencode/plugin";
import { setup } from "./setup.ts";

export default Plugin.define({
  id: "vibe-coding-v2",
  // Explicit host boundary; the target SDK and provider-backed smoke must be verified before release.
  async setup(ctx) { await setup(ctx as unknown as Parameters<typeof setup>[0]); },
});
