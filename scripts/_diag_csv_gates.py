import csv
from industry_gate import check_industry_gate
from utils import init_pipeline_prefs, load_candidate_preferences
from zero_shot_classifier import classify_onsite, resolve_location_verdict

init_pipeline_prefs()
prefs = load_candidate_preferences()
path = r"C:\Users\Jason\Downloads\Job Evaluation 1 - Sheet1.csv"
targets = ["Pinterest", "Lendbuzz", "Payanywhere", "Yahoo"]

with open(path, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row["Company"] not in targets:
            continue
        jd = row["Job Description"]
        co = row["Company"]
        pos = row["Position"]
        rej, reason = classify_onsite(jd, prefs)
        verdict, detail = resolve_location_verdict(jd, prefs)
        ind_ok, ind_reason = check_industry_gate(co, jd, pos, prefs)
        print(f"=== {co} ===")
        print(f"position: {pos}")
        print(f"onsite reject: {rej} | {reason}")
        print(f"verdict: {verdict} | {detail}")
        print(f"industry pass: {ind_ok} | {ind_reason}")
        low = jd.lower()
        for pat in [
            "remote",
            "est",
            "eastern",
            "cst",
            "central",
            "onsite",
            "on-site",
            "hybrid",
            "gaming",
            "games",
            "gambling",
        ]:
            if pat in low:
                idx = low.find(pat)
                print(f"  hit '{pat}': ...{jd[max(0, idx - 50): idx + 70].replace(chr(10), ' ')}...")
        print()
