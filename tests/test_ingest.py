import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_autopsy.ingest import (ingest, ingest_anthropic, ingest_jsonl,
                                 ingest_openai)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_jsonl_roundtrip(tmp_path):
    p = _write(tmp_path, "t.jsonl",
               '{"step": 0, "role": "user", "kind": "message", "text": "hi"}\n'
               '{"step": 1, "role": "assistant", "kind": "tool_call", '
               '"tool": "search", "args": {"q": "x"}}\n')
    evs = ingest_jsonl(p)
    assert len(evs) == 2
    assert evs[1]["tool"] == "search" and evs[1]["args"] == {"q": "x"}


def test_openai_tool_calls():
    obj = {"messages": [
        {"role": "user", "content": "find it"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "function": {"name": "search",
                                     "arguments": '{"q": "it"}'}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "found it"},
    ]}
    evs = ingest_openai(obj)
    kinds = [e["kind"] for e in evs]
    assert kinds == ["message", "tool_call", "tool_result", "message"] or \
        "tool_call" in kinds
    tc = next(e for e in evs if e["kind"] == "tool_call")
    assert tc["tool"] == "search" and tc["args"] == {"q": "it"}
    tr = next(e for e in evs if e["kind"] == "tool_result")
    assert tr["tool"] == "search" and tr["text"] == "found it"


def test_anthropic_blocks():
    obj = {"messages": [
        {"role": "user",
         "content": [{"type": "text", "text": "find it"}]},
        {"role": "assistant", "content": [
            {"type": "text", "text": "searching"},
            {"type": "tool_use", "id": "u1", "name": "search",
             "input": {"q": "it"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "u1",
             "content": "found it"}]},
    ]}
    evs = ingest_anthropic(obj)
    tc = next(e for e in evs if e["kind"] == "tool_call")
    assert tc["tool"] == "search"
    tr = next(e for e in evs if e["kind"] == "tool_result")
    assert tr["tool"] == "search" and not tr["error"]


def test_auto_detect_jsonl(tmp_path):
    p = _write(tmp_path, "t.jsonl",
               '{"role": "assistant", "kind": "message", "text": "a"}\n'
               '{"role": "assistant", "kind": "message", "text": "b"}\n')
    assert len(ingest(p)) == 2


def test_auto_detect_openai(tmp_path):
    p = _write(tmp_path, "t.json",
               json.dumps({"messages": [{"role": "user",
                                         "content": "hi"}]}))
    evs = ingest(p)
    assert evs and evs[0]["role"] == "user"
