"""Run the attribution + resume-verdict evaluation over the corpus.

Metrics:
  attribution: exact-step hit, near hit (|pred-true|<=2), top-3 hit,
               mean absolute step distance
  verdict: accuracy + per-class precision/recall
Writes eval/results.json and prints a table. All numbers measured.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_autopsy.attribution import attribute, primary_mode  # noqa: E402
from agent_autopsy.resume import resume_verdict  # noqa: E402
from eval.corpus import build_corpus  # noqa: E402


def evaluate(corpus):
    rows = []
    for t in corpus:
        res = attribute(t["events"])
        ver = resume_verdict(res, t["events"])
        pred = res.culprit_step
        true = t["true_culprit"]
        top3 = [a.step for a in res.per_step[:3]]
        if true is None:
            hit_exact = (pred is None)
            hit_near = hit_exact
            hit_top3 = hit_exact  # no culprit to rank; correct = finding none
            dist = 0 if hit_exact else None
        else:
            hit_exact = (pred == true)
            hit_near = pred is not None and abs(pred - true) <= 2
            hit_top3 = true in top3
            dist = abs(pred - true) if pred is not None else None
        rows.append({
            "fault": t["fault"], "seed": t["seed"],
            "true_culprit": true, "pred_culprit": pred,
            "hit_exact": hit_exact, "hit_near": hit_near,
            "hit_top3": hit_top3,
            "dist": dist,
            "true_mode": t["true_mode"],
            "pred_mode": primary_mode(res),
            "expected_verdict": t["expected_verdict"],
            "pred_verdict": ver["verdict"],
        })
    return rows


def summarize(rows):
    by_fault = {}
    for r in rows:
        by_fault.setdefault(r["fault"], []).append(r)
    table = {}
    for fault, rs in by_fault.items():
        n = len(rs)
        table[fault] = {
            "n": n,
            "attrib_exact": sum(r["hit_exact"] for r in rs) / n,
            "attrib_near": sum(r["hit_near"] for r in rs) / n,
            "attrib_top3": sum(r["hit_top3"] for r in rs) / n,
            "mean_dist": (sum(r["dist"] for r in rs if r["dist"] is not None)
                          / max(1, sum(1 for r in rs if r["dist"] is not None))),
            "verdict_acc": sum(r["pred_verdict"] == r["expected_verdict"]
                               for r in rs) / n,
        }
    # verdict per-class P/R over non-clean rows
    classes = sorted({r["expected_verdict"] for r in rows})
    pr = {}
    for c in classes:
        tp = sum(1 for r in rows if r["expected_verdict"] == c
                 and r["pred_verdict"] == c)
        fp = sum(1 for r in rows if r["expected_verdict"] != c
                 and r["pred_verdict"] == c)
        fn = sum(1 for r in rows if r["expected_verdict"] == c
                 and r["pred_verdict"] != c)
        pr[c] = {"precision": tp / (tp + fp) if tp + fp else 0.0,
                 "recall": tp / (tp + fn) if tp + fn else 0.0,
                 "support": tp + fn}
    faulty = [r for r in rows if r["fault"] != "clean"]
    overall = {
        "n_traces": len(rows),
        "attrib_exact": sum(r["hit_exact"] for r in faulty) / len(faulty),
        "attrib_near": sum(r["hit_near"] for r in faulty) / len(faulty),
        "attrib_top3": sum(r["hit_top3"] for r in faulty) / len(faulty),
        "verdict_acc": sum(r["pred_verdict"] == r["expected_verdict"]
                           for r in rows) / len(rows),
        "clean_false_positive_rate": sum(
            1 for r in rows if r["fault"] == "clean"
            and r["pred_culprit"] is not None) / sum(
                1 for r in rows if r["fault"] == "clean"),
    }
    return {"overall": overall, "by_fault": table, "verdict_pr": pr}


def main():
    dev = build_corpus(seeds_per_type=12, seed0=1000, scenario="research")
    heldout = build_corpus(seeds_per_type=12, seed0=9000, scenario="debug")
    for name, corpus in (("dev(research)", dev), ("heldout(debug)", heldout)):
        rows = evaluate(corpus)
        summary = summarize(rows)
        print(f"===== {name}: {len(corpus)} traces =====")
        o = summary["overall"]
        print(f"attribution exact : {o['attrib_exact']:.3f}")
        print(f"attribution ±2    : {o['attrib_near']:.3f}")
        print(f"attribution top-3 : {o['attrib_top3']:.3f}")
        print(f"verdict accuracy  : {o['verdict_acc']:.3f}")
        print(f"clean-trace false-positive rate: "
              f"{o['clean_false_positive_rate']:.3f}")
        print()
        outdir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(outdir, exist_ok=True)
        tag = "dev" if name.startswith("dev") else "heldout"
        with open(os.path.join(outdir, f"results_{tag}.json"), "w") as f:
            json.dump({"summary": summary, "rows": rows}, f, indent=1)


if __name__ == "__main__":
    main()
