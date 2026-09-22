# Core extraction

The source framework had 31 Skills, OpenCode roles/commands, provider definitions, MCP entries, TypeScript plugins, and runtime state.

This global package preserves the core that affects day-to-day Vibe Coding behavior:

1. the Vibe Coding primary-agent persona and authority/lifecycle rules;
2. 31 task Skills, including a Codex-native dynamic subagent-orchestration Skill;
3. eight role templates and a deterministic prompt renderer for bounded Codex subagent delegation;
4. persistent global workflow runtime and project-log initializer;
5. a small MCP toolbelt chosen by task coverage rather than exact OpenCode parity.

It deliberately avoids copying implementation-specific OpenCode providers, agent formats, commands, plugins, credentials, and historical state.
