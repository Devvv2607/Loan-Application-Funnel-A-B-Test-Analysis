"""Phase 10: render the claims registry and resume bullets.

Every finding stated in prose is a template whose numbers are looked up from
output files at render time. A missing metric, or a claim whose stated
precondition no longer holds (e.g. "the truth lies inside the CI"), fails the
build instead of shipping a stale sentence.
"""

from __future__ import annotations

import yaml

from common import ROOT, read_json, write_json


class ClaimError(RuntimeError):
    pass


def resolve(ref: str):
    fname, _, path = ref.partition(":")
    obj = read_json(f"outputs/{fname}")
    for part in path.split("."):
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            raise ClaimError(f"Missing metric: {ref}")
    if obj is None:
        raise ClaimError(f"Null metric: {ref}")
    return obj


def render_all() -> list[dict]:
    reg = yaml.safe_load((ROOT / "outputs" / "claims.yaml").read_text(encoding="utf-8"))
    out = []
    for c in reg["claims"]:
        values = {k: resolve(ref) for k, ref in c["metrics"].items()}
        for ref, expected in (c.get("requires") or {}).items():
            if resolve(ref) != expected:
                raise ClaimError(f"{c['id']}: precondition {ref} == {expected} no longer holds")
        out.append({"id": c["id"], "text": c["template"].format(**values), "template": c["template"],
                    "metrics": {k: {"ref": c["metrics"][k], "value": v} for k, v in values.items()},
                    "sources": sorted({ref.split(":")[0] for ref in c["metrics"].values()})})
    return out


def resume_bullets(claims: dict) -> str:
    t = {k: v["text"] for k, v in claims.items()}
    m = {k: {n: x["value"] for n, x in v["metrics"].items()} for k, v in claims.items()}
    e, g = m["EXP-001"], m["GRD-001"]
    return "\n".join([
        "# Resume bullet drafts (simulated-data project)",
        "",
        "> All figures come from a simulated dataset with planted effects (fictional lender). Say so on the resume.",
        "",
        f"- Built an end-to-end SQL (DuckDB) funnel analysis on a simulated loan event log "
        f"({m['FUN-001']['started']:,} pre-period applicants); identified KYC as the largest drop-off ({m['FUN-002']['share']:.0%} of all drop-off).",
        f"- Pre-registered and analysed a simulated A/B test of a simplified KYC flow: {e['diff']:+.1f} pp KYC "
        f"completion (95% CI {e['lo']:.1f}–{e['hi']:.1f} pp), recovering the planted true effect inside the CI.",
        f"- Designed a break-even non-inferiority guardrail on early-delinquent loans per 1,000 users; result "
        f"{g['label']} (bound {g['b']:+.1f} vs +{g['m']}), leading to a pre-registered \"{m['DEC-001']['decision']}\" "
        f"call instead of an unsupported ship.",
        f"- Validated the method by simulation: A/A false-positive rate {m['VAL-001']['fpr']:.1%}, CI coverage "
        f"{m['VAL-002']['cov']:.1%}, SRM detection of a broken split, and a peeking demo "
        f"({m['VAL-004']['peek']:.0%} vs {m['VAL-004']['fixed']:.0%} false positives).",
        "",
        "Source claims: " + ", ".join(sorted(t)),
        "",
    ])


def main() -> None:
    rendered = render_all()
    write_json("outputs/claims_rendered.json", {"simulated": True, "claims": rendered})
    by_id = {c["id"]: c for c in rendered}
    (ROOT / "outputs" / "resume_bullets.md").write_text(resume_bullets(by_id), encoding="utf-8", newline="\n")
    for c in rendered:
        print(f"{c['id']}: {c['text']}")


if __name__ == "__main__":
    main()
