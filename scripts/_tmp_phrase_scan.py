import re
from pathlib import Path

companies = ["BenefitHub","Runpod","LTK","union_home_mortgage_corp","Yext","the_judge_group","avenue_code","exl"]
base = Path("data/submissions")
word_phrases = ["streamline","streamlined","leverage","robust","cutting-edge","utilize","facilitate","empower","delve","transformative","tapestry","genuinely"]
multi_phrases = ["serves as","would welcome","is the kind of","Rather than","instead of","not as a","Ambiguity Navigation"]
ing_re = re.compile(r",\s+(\w+ing)\b", re.I)
bullet_re = re.compile(r"^\s*[\*\-]\s+")

for c in companies:
    print("=====", c, "=====")
    all_ing = []
    all_phrases = []
    for fname in ["Resume.md","CoverLetter.md"]:
        path = base / c / fname
        if not path.exists():
            print("MISSING:", fname)
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if bullet_re.match(line):
                ms = list(ing_re.finditer(line))
                if ms:
                    verbs = [m.group(1).lower() for m in ms]
                    all_ing.append((fname, verbs, line.strip()))
        for p in word_phrases:
            for m in re.finditer(r"\b" + re.escape(p) + r"\b", text, re.I):
                start = max(0, m.start()-40)
                end = min(len(text), m.end()+60)
                ctx = re.sub(r"\s+", " ", text[start:end]).strip()
                all_phrases.append((fname, p, ctx))
        for p in multi_phrases:
            for m in re.finditer(re.escape(p), text, re.I):
                start = max(0, m.start()-40)
                end = min(len(text), m.end()+60)
                ctx = re.sub(r"\s+", " ", text[start:end]).strip()
                all_phrases.append((fname, p, ctx))
    print("ING_BULLETS:", len(all_ing))
    for fname, verbs, line in all_ing:
        print("  ING", fname, verbs, "|", line[:160])
    print("PHRASE_HITS:", len(all_phrases))
    for fname, p, ctx in all_phrases:
        print("  PHRASE", fname, p, "|", ctx)
    print()
