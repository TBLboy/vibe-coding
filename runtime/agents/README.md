# Vibe Coding dynamic subagent roles

These are **role templates**, not independent persistent Codex runtimes. The global Vibe Goal
main agent reads the selected template and delegates it through Codex's native subagent mechanism
when that mechanism is available.

The main agent keeps final authority, user interaction, project-log consistency, integration, and
any C-level decision. A role may only receive the project scope, task contract, files, and write
permissions explicitly passed to it.

If native delegation is unavailable, execute the same role contract serially and label the result
`serial-role-fallback`; do not falsely claim an independent subagent performed the work.
