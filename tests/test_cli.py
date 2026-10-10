import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_autopsy.cli import main
from eval.corpus import make_trace


def _trace_file(tmp_path, fault="poison_injection"):
    t = make_trace(fault, 1000)
    p = tmp_path / "trace.jsonl"
    with open(p, "w") as f:
        for e in t["events"]:
            f.write(json.dumps(e) + "\n")
    return str(p), t


def test_cli_text_output(tmp_path, capsys):
    p, t = _trace_file(tmp_path)
    assert main([p]) == 0
    out = capsys.readouterr().out
    assert "AGENT AUTOPSY REPORT" in out
    assert f"step {t['true_culprit']}" in out
    assert "DO_NOT_RESUME" in out


def test_cli_html_and_json(tmp_path, capsys):
    p, _ = _trace_file(tmp_path, "loop_stall")
    html = str(tmp_path / "r.html")
    js = str(tmp_path / "r.json")
    assert main([p, "--html", html, "--json", js, "--quiet"]) == 0
    assert os.path.exists(html) and os.path.exists(js)
    payload = json.load(open(js))
    assert payload["failure_found"] is True
    assert payload["verdict"]["verdict"] == "RESUME_WITH_FIX"
    assert "Autopsy" in open(html).read()


def test_cli_empty_trace(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    assert main([str(p)]) == 2
