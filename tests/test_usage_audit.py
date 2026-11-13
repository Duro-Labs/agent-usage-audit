import datetime as dt
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "usage-audit"
LOADER = importlib.machinery.SourceFileLoader("usage_audit", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


def write_records(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


class UsageAuditTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.now = dt.datetime.now(dt.timezone.utc)
        self.inside = self.now.isoformat()
        self.outside = (self.now - dt.timedelta(hours=7)).isoformat()
        self.cutoff = self.now - dt.timedelta(hours=5)

    def test_claude_deduplicates_streamed_request_and_includes_subagent(self):
        path = self.home / ".claude/projects/work/session/subagents/agent-12345678.jsonl"
        usage = {"input_tokens": 2, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20, "output_tokens": 9}
        rows = [
            {"type": "assistant", "timestamp": self.outside, "requestId": "old", "message": {"model": "opus", "usage": usage}},
            {"type": "assistant", "timestamp": self.inside, "requestId": "one", "effort": "high", "cwd": "/work", "message": {"model": "opus", "usage": usage, "content": [{"type": "tool_use", "name": "SendMessage", "id": "tool-one", "input": {"message": "handoff"}}]}},
            {"type": "assistant", "timestamp": self.inside, "requestId": "one", "effort": "high", "message": {"model": "opus", "usage": usage, "content": [{"type": "tool_use", "name": "SendMessage", "id": "tool-one", "input": {"message": "handoff"}}]}},
            {"type": "user", "timestamp": self.inside, "message": {"content": [{"type": "tool_result", "content": "large result"}]}},
            {"type": "system", "timestamp": self.inside, "subtype": "compact_boundary"},
        ]
        write_records(path, rows)
        result = MODULE.claude_session(path, self.cutoff)
        self.assertEqual(result["requests"], 1)
        self.assertEqual(result["median_context"], 122)
        self.assertEqual(result["totals"], {"input": 2, "cached": 100, "written": 20, "output": 9})
        self.assertEqual(result["efforts"], {"high": 1})
        self.assertTrue(result["subagent"])
        self.assertEqual(result["compactions"], 1)
        self.assertEqual(result["tool_result_bytes"], len("large result"))
        self.assertEqual((result["handoffs"], result["handoff_bytes"]), (1, len("handoff")))

    def test_codex_uses_response_usage_once_and_separates_cached_input(self):
        path = self.home / ".codex/sessions/2026/11/13/rollout-2026-11-13T12-00-00-abcdef12.jsonl"
        usage = {"input_tokens": 200, "cached_input_tokens": 150, "cache_write_input_tokens": 0, "output_tokens": 30}
        rows = [
            {"type": "session_meta", "timestamp": self.outside, "payload": {"cwd": "/repo"}},
            {"type": "turn_context", "timestamp": self.inside, "payload": {"turn_id": "turn", "model": "gpt", "effort": "medium"}},
            {"type": "token_usage_record", "timestamp": self.inside, "payload": {"response_id": "response", "turn_id": "turn", "usage": usage}},
            {"type": "token_usage_record", "timestamp": self.inside, "payload": {"response_id": "response", "turn_id": "turn", "usage": usage}},
            {"type": "event_msg", "timestamp": self.inside, "payload": {"type": "token_count", "info": {"last_token_usage": usage}}},
            {"type": "response_item", "timestamp": self.inside, "payload": {"type": "custom_tool_call_output", "output": "tool output"}},
        ]
        write_records(path, rows)
        result = MODULE.codex_session(path, self.cutoff)
        self.assertEqual(result["requests"], 1)
        self.assertEqual(result["median_context"], 200)
        self.assertEqual(result["totals"], {"input": 50, "cached": 150, "written": 0, "output": 30})
        self.assertEqual(result["models"], {"gpt": 1})
        self.assertEqual(result["efforts"], {"medium": 1})
        self.assertEqual(result["tool_result_bytes"], len("tool output"))

    def test_workspace_groups_exact_sessions_and_marks_directory_fallback(self):
        sessions = [
            {"provider": "claude", "session_id": "exact", "cwd": "/shared"},
            {"provider": "codex", "session_id": "unknown", "cwd": "/crm"},
            {"provider": "codex", "session_id": "elsewhere", "cwd": "/other"},
        ]
        workspace = {
            "members": {("claude", "exact"): "research"},
            "unresolved": [{"provider": "codex", "tab": "crm", "cwd": "/crm"}],
        }
        exact = MODULE.group_workspace(sessions, workspace)
        self.assertEqual([(item["session_id"], item["tab"]) for item in exact], [("exact", "research")])
        with_cwd = MODULE.group_workspace(sessions, workspace, match_cwd=True)
        self.assertEqual([(item["session_id"], item["membership"]) for item in with_cwd], [("exact", "session ID"), ("unknown", "working directory")])

    def test_instruction_files_include_each_workspace_charter(self):
        charter = self.home / ".claude/workspaces/example.md"
        charter.parent.mkdir(parents=True)
        charter.write_text("one charter")
        self.assertEqual(MODULE.instruction_files(self.home), [{"path": str(charter), "bytes": len("one charter")}])


if __name__ == "__main__":
    unittest.main()
