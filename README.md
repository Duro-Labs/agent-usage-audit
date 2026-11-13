# Local usage audit

`./usage-audit` reads local Claude Code and Codex JSONL session records and reports which sessions carry the largest input contexts. It uses only the Python standard library. It does not call a model, use the network, or print prompt and tool-result contents.

```bash
./usage-audit
./usage-audit --provider claude --hours 24 --top 5
./usage-audit --provider codex --hours 24 --top 5
./usage-audit --workspace 'Your workspace' --hours 5
./usage-audit --workspace 'Your workspace' --match-cwd --hours 5
./usage-audit --hours 168 --json
```

The default lookback is five hours. The report includes Claude subagents found under `~/.claude/projects/`, Codex sessions under `~/.codex/sessions/`, model and effort counts, response counts, median/90th-percentile/maximum input context, fresh and cached input, output tokens, largest serialized user item and tool result, Claude `SendMessage` handoff count and text size, compaction count where recorded, and sizes of the standing Claude and Codex instruction files. `--home PATH` selects another home directory for testing or a local archive.

Claude's repeated assistant records are deduplicated by request ID. Codex's `token_usage_record` entries are deduplicated by response ID. The tool uses each request's recorded timestamp, so long histories contribute only requests in the lookback window. Recent files are selected by modification time before parsing. A partial record or unavailable file is skipped.

These numbers are diagnostics, not a bill or a plan-limit meter. Cached input has different accounting from fresh input; the script does not infer a subscription credit cost or five-hour quota percentage. User-item byte sizes can include image data and metadata, so they are not token estimates. File sizes are bytes on disk and do not prove those files were injected into a particular session. For actual plan usage, check Claude's Settings > Usage and the corresponding Codex account usage display.

`--workspace` queries the local Herdr workspace, tab, and pane lists and groups active session IDs across tabs. It shows one workspace total, a breakdown by tab, and the largest individual sessions. Subagents stored under a Claude session are included with their parent tab. Historical sessions no longer attached to a pane are excluded. If Herdr does not report a pane's session ID, the report names it as unresolved. `--match-cwd` additionally includes sessions whose recorded working directory matches that pane; this can count unrelated sessions started from the same folder, so the output marks those rows as working-directory matches. Herdr must be running for workspace grouping; ordinary provider reports work without it.
