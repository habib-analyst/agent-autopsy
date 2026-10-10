import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_autopsy.attribution import attribute, primary_mode
from agent_autopsy.resume import resume_verdict
from eval.corpus import make_trace


def _autopsy(fault, seed=1000, scenario="research"):
    t = make_trace(fault, seed, scenario=scenario)
    res = attribute(t["events"])
    ver = resume_verdict(res, t["events"])
    return t, res, ver


def test_poison_attribution_and_verdict():
    t, res, ver = _autopsy("poison_injection")
    assert res.failure_found
    assert res.culprit_step == t["true_culprit"]
    assert primary_mode(res) == "context_poisoning"
    assert ver["verdict"] == "DO_NOT_RESUME"
    assert ver["resume_from_step"] is None


def test_misuse_verdict():
    t, res, ver = _autopsy("tool_misuse")
    assert res.culprit_step == t["true_culprit"]
    assert ver["verdict"] == "RESUME_WITH_FIX"
    assert ver["resume_from_step"] == t["true_culprit"]


def test_loop_onset_attribution():
    t, res, ver = _autopsy("loop_stall")
    assert res.culprit_step == t["true_culprit"]  # onset, not mid-loop


def test_drift_attribution():
    t, res, ver = _autopsy("plan_drift")
    assert res.culprit_step == t["true_culprit"]
    assert ver["verdict"] == "RESUME_WITH_FIX"


def test_premature_verdict():
    t, res, ver = _autopsy("premature_termination")
    assert res.culprit_step == t["true_culprit"]
    assert ver["verdict"] == "SAFE_TO_RESUME"


def test_transient_verdict():
    t, res, ver = _autopsy("transient")
    assert res.culprit_step == t["true_culprit"]
    assert ver["verdict"] == "SAFE_TO_RESUME"


def test_clean_trace_no_failure():
    t, res, ver = _autopsy("clean")
    assert not res.failure_found
    assert res.culprit_step is None
    assert ver["verdict"] == "NO_FAILURE_FOUND"


def test_generalizes_to_heldout_scenario():
    for fault in ["poison_injection", "loop_stall", "plan_drift", "clean"]:
        t, res, ver = _autopsy(fault, seed=9000, scenario="debug")
        assert res.culprit_step == t["true_culprit"], fault
        assert ver["verdict"] == t["expected_verdict"], fault
