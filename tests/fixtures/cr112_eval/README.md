# CR-112 frozen eval set (sanitized)

Five practice JDs. Fictional companies. No live employer folders, no candidate PII.

`scripts/run_cr112_eval.py` copies these into `data/eval/cr112/` at runtime. That output directory is gitignored. Default is `--paid-llm` off. Do not point the runner at production `jobagent.sqlite`.
