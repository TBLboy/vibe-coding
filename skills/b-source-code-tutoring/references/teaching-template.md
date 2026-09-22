# Source-Grounded Code Explanation Template

Use this template for a non-trivial asynchronous or stateful path.

## Path

```text
<external input/event>
→ <entry method>
→ <decision/policy>
→ <message/output type>
→ <downstream handler>
→ <result callback/terminal state>
```

## Concrete Input

```text
<input field>=<example value>
```

## Runtime Timeline

```text
t=0   ...
t=1   ...
```

## State Lifecycle

| Variable/object | Initial | Written by | Read by | Effect | Reset/terminal |
|---|---|---|---|---|---|
| | | | | | |

## Source Walkthrough

1. `<file>:<symbol>`: caller, inputs, and early returns.
2. `<file>:<symbol>`: object construction and field assignment.
3. `<file>:<symbol>`: outbound boundary and receiving consumer.
4. `<file>:<symbol>`: result handling and state release.

## Engineering Interpretation

```text
Confirmed source facts:
- ...

Pattern name, if useful:
- ...

Not yet verified/read:
- ...
```

## Next Boundary

```text
Continue from <file>:<symbol> because it consumes <object/message>.
```
