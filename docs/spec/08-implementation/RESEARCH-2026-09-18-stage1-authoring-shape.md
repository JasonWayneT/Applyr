# Stage 1 authoring shape: research and recommendation

Status: research recommendation. CR-120 now scopes a subscription-first evidence-plan candidate with a dedicated editorial pass; its quality and release gates supersede the lower-cost three-arm experiment proposed below. Years-range work remains CR-117.

## Decision question

Which Stage 1 workflow gives Jason the strongest truthful, role-specific resume and cover letter with the least review and repair effort, without excessive authoring cost?

## Local evidence

- Stage 0 currently provides a bounded packet with JD items, selected evidence, source excerpts, attribution constraints, soft gaps, and an ATS term contract. Stage 1 sends that packet and a rule digest to one external author session, which returns Resume.md, CoverLetter.md, and claim_provenance.json. See `scripts/build_authoring_packet.py`, `scripts/author_from_packet.py`, and `docs/spec/08-implementation/CR-074-authoring-prompt.md`.
- The Camunda first draft had no identified fabrication, employer misattribution, or extra-packet citation. Its documented weaknesses were underuse of a selected metric, a JD-paraphrasing opening, repeated resume/letter wording, and incomplete provenance. The report is one case, not a measured failure distribution. See `docs/spec/08-implementation/CR-112-camunda-first-draft-quality-root-cause.md`.
- Stage 1 already has mechanical quality, repetition, specificity, provenance, and evidence-use checks. Verification history and a five-JD fictional fixture set exist, but the fixture set has not established a Stage 1 quality baseline. See `scripts/author_from_packet.py`, `scripts/run_cr112_eval.py`, and `tests/fixtures/cr112_eval/README.md`.

## External evidence and limits

- Berkeley Career Engagement recommends selecting accomplishments against the position description, showing outcomes, and quantifying results where possible. This supports evidence selection as part of authoring, not just keyword matching. https://www.career.berkeley.edu/prepare-for-success/resumes/
- ACL 2024 studies found that planning before grounded long-form generation improved attribution, and that selecting source segments before writing improved local attribution while preserving or improving generation quality in tested tasks. These were question answering and summarization tasks, not resumes. https://aclanthology.org/2024.acl-long.615/ and https://aclanthology.org/2024.acl-long.182/
- Anthropic describes prompt chaining for work that divides cleanly into fixed steps and evaluator/optimizer loops when clear feedback measurably improves drafts. It advises starting with simpler workflows and adding complexity when evaluation shows value. https://www.anthropic.com/engineering/building-effective-agents
- A separate ACL study found mixed results for content planning: plans optimized for automatic metrics could score better mechanically while doing worse under human judgment. This is a warning against making rubric scores the sole success measure. https://aclanthology.org/2024.eacl-long.142/
- Human expert preference remains important for complex writing quality; automated graders are useful proxies but do not replace it. https://openai.com/index/gdpval/ and https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

## Options considered

| Shape | Likely benefit | Main weakness | Decision |
| --- | --- | --- | --- |
| Current one-pass author plus repair | Cheapest and already grounded | Author must decide evidence allocation, write two documents, and record provenance at once | Keep as control |
| Deterministic blueprint plus one author | Cheap, reproducible evidence allocation | Ranking code cannot reliably choose the best narrative or divide facts between resume and letter; may overfit gates | Test as a lower-cost challenger |
| Evidence-first plan, then compose, then validate and repair | Separates content choices from phrasing; allows checking evidence allocation before prose | Extra model call and risk of formulaic plans | Recommended candidate |
| Independent authors for resume and letter | Focused document prompts | More calls; greater chance of repetition and inconsistent positioning | Reject for default path |
| Multi-agent debate or autonomous agent | Flexible critique | High cost and orchestration; fixed task does not require open-ended delegation | Reject for default path |
| Fine-tuned or template-only generator | Potential scale efficiency | Training data and maintenance burden; weak fit for a small, evolving personal evidence base | Defer |

## Recommended Stage 1 shape

1. **Evidence plan.** Give one planner the Stage 0 packet. It returns a small structured plan: resume bullet slots by role, supporting claim IDs and exact source spans, key JD need served, metric to preserve, attribution limit, skills-row facts, and a separate cover-letter argument with distinct proof. It also marks evidence intentionally omitted. The plan contains no polished prose or invented claims.
2. **Plan gate.** Check that every selected ID and fact is in the packet, every role has an honest source, attribution is correct, required/soft-gap needs are addressed as far as the packet allows, and selected proof fits the one-page bullet budget. Unsupported plan rows are repaired or removed before drafting.
3. **Compose together.** One author writes both documents from the packet and checked plan in the same session. Writing the pair together preserves one positioning and makes repetition easier to avoid. The author records provenance for every factual resume unit, including Core Competencies, and every factual cover-letter sentence.
4. **Validate and repair.** Run existing mechanical checks. Return a short, ranked defect list to the author for one focused repair. Re-run checks, then perform a separate human-style read for voice, relevance, proof density, and whether the cover letter adds an argument. Keep the current bounded stop condition for unresolved failures.

The plan is the only proposed new intermediate artifact. It should remain outside the final submission and use the same closed-world evidence as the current packet. A schema-constrained response would help if Stage 1 moves to an API, but schema validity alone does not prove factual support.

## Decision test before changing the default

Run three variants on the same frozen JD/packet set with the same author model and review rubric: current workflow, deterministic blueprint plus one author, and evidence-first plan plus author. Include the existing fictional fixtures and a small privacy-safe set that covers narrow, broad, and soft-gap roles. Do not tune on the evaluation set.

Record first-draft and post-repair results separately: unsupported or misattributed claims, missed high-value evidence, provenance completeness, mechanical pass rate, human blind preference for resume and letter as a pair, repair rounds, elapsed time, and model/token cost. Jason's blind send/one-pass/rework judgment is the primary quality outcome. A candidate wins only if it improves that outcome without raising truth errors or cost beyond an agreed budget. If the two-call plan does not beat the cheaper one-call blueprint, keep the simpler workflow.

## Open design questions

- How much additional Stage 1 time or subscription usage is acceptable for a materially better first draft?
- Should the planner be a separate model call, or a first response in one bounded author session? Both should be measured; the content contract is the same.
- Does the current sentence-level provenance format need a typed `resume_unit` for Core Competencies and summary claims before testing? The Camunda case suggests yes, but this should be specified from actual validator behavior.

This recommendation is an inference from adjacent research and one documented Applyr draft. The comparative test is needed before calling it the best-performing production design.
