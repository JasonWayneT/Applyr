# IMP-CR-036: Solo PM Trap + Years Policy Lock

**CR:** CR-036  
**Requirements:** FR-109 (extend), FR-189  
**Status:** Completed 2026-06-02

## Summary

- `solo_pm_gate.py` — zero-token reject for sole/founding/first PM; allow squad org + mentorship
- `fit_policy.years_lock_prompt_block` — prevents LLM re-penalizing 7-year cap
- `seniority_gate.py` — improved years regex patterns
- Preference: `avoid_solo_pm_trap` replaces `no_people_management`

## Verification

```bash
python scripts/test_seniority_years_gate.py
python scripts/test_solo_pm_gate.py
python scripts/test_batch_gate.py
python scripts/evaluate_jd_only.py data/debug_dailypay_jd.txt DailyPay
```
