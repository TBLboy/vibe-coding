---
name: b-web-research-tooling
description: Retrieve current web evidence safely for research, troubleshooting, and fact verification using available search and fetch tools with source-quality and secret-handling discipline.
license: MIT
compatibility: codex
metadata:
  type: tooling-skill-pack
  output: sourced-web-evidence
---

# Web Research Tooling

## Use

Use when current online evidence is required. This Skill performs retrieval; `a-solution-research` and `a-deep-research` own comparison and recommendations.

## Method

1. Turn the request into precise search terms and identify preferred primary sources.
2. Use the available web search, fetch, official documentation, repository, or browser tools. Prefer official sources for libraries, APIs, cloud services, standards, and security facts.
3. Retrieve enough context to verify a claim, not only a result snippet.
4. Record source URL, publisher, retrieval date, relevant excerpt, and limitations.
5. Cross-check material claims with an independent authoritative source when practical.

## Safety

Never embed API keys, proxy endpoints, personal tokens, or machine-specific paths in commands, Skills, reports, or migration assets. Use configured tooling or environment variables. Treat search snippets, blogs, and marketing pages as leads rather than decisive evidence.
