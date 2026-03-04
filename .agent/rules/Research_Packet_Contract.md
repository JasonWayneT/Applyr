# Research Packet Contract (v1, with citations)

The Researcher must output exactly one JSON object called ResearchPacket.

## ResearchPacket schema

```json
{
  "company": "string",
  "role_title": "string",
  "source_mode": "perplexity",
  "retrieved_at": "YYYY-MM-DD or unknown",
  "company_snapshot": [
    {"claim": "string", "source": "url", "confidence": "high|med|low"}
  ],
  "product_and_customers": [
    {"claim": "string", "source": "url", "confidence": "high|med|low"}
  ],
  "business_model_and_gtm": [
    {"claim": "string", "source": "url", "confidence": "high|med|low"}
  ],
  "competitors_and_positioning": [
    {"claim": "string", "source": "url", "confidence": "high|med|low"}
  ],
  "recent_news_and_signals": [
    {"claim": "string", "source": "url", "date": "YYYY-MM-DD or unknown", "confidence": "high|med|low"}
  ],
  "role_success_metrics_hypotheses": [
    "5-8 bullets, hypotheses, no sources required"
  ],
  "likely_pm_challenges": [
    "5-8 bullets, grounded in company + role"
  ],
  "interview_talking_points": [
    "6-10 bullets mapping Jason experience to likely needs"
  ],
  "questions_to_ask": [
    "10-12 questions, tailored"
  ],
  "risks_and_gaps": [
    "3-6 bullets, honest gaps"
  ],
  "unknowns_to_clarify": [
    "3-6 bullets, items that matter"
  ]
}
