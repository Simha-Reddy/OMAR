# National Title Tag Policy: Overview, Tuning, and Trade‑offs

This document explains how note "tagging" works in the refactored OMAR retrieval pipeline, how to configure the tag policy, and the pros/cons of using it.

## What it does

- Each note has a nationalTitle (with fallback to local title when missing) stored in the document index meta and exposed to the query model.
- A regex-based classifier (app/query/query_models/default/services/title_tagging.py) assigns one or more domain tags to each title (e.g., primary care, nursing, education, mental health, outside, home health, functional, administrative, social work).
- Each tag contributes a configurable score boost (tag_boost) that gets injected directly into hybrid retrieval scoring (BM25 + boosts) BEFORE the top_k cut.
- The goal is to nudge the retriever toward clinically salient notes (e.g., primary care) and downweight low-yield types (e.g., purely administrative) while keeping the rest of the ranking influences (query match, section/title match, recency) intact.

## Where it lives (files)

- Tagging rules and defaults:
  - app/query/query_models/default/services/title_tagging.py
    - TAGS, DEFAULT_TAG_POLICY
    - tag_title(), score_for_title(), score_for_tags()
- Injection into retrieval:
  - app/query/query_models/default/services/rag.py
    - hybrid_search() reads per-chunk tag_boost and adds to the score
- Source of titles:
  - app/services/document_search_service.py
    - DocumentSearchIndex.meta includes nationalTitle

## How the boost is computed

- For each chunk, the provider computes a tag_boost from the nationalTitle (fallback: title/section) using the policy weights.
- tag_boost is additive to the scoring term in hybrid_search() alongside other boosts like section match and recency.
- The weights are small, relative nudges, not hard filters. They should not dominate strong lexical or semantic matches.

## Tuning the policy (per request)

You can override the default policy on a per-request basis via the unified /api/query/ask endpoint by passing tag_policy in the request body. The same works for /api/query/rag_results.

Example: boost primary care more, de‑emphasize administrative and nursing further, and leave others as default.

```
POST /api/query/ask
Content-Type: application/json

{
  "query": "When was metformin started?",
  "patient": { "DFN": "123" },
  "tag_policy": {
    "primary_care": 1.3,
    "administrative": -0.5,
    "nursing": -0.3
  }
}
```

Notes:
- Missing tags in the override fall back to DEFAULT_TAG_POLICY.
- Values are additive magnitudes; typical useful range is about -1.0 .. +1.5. Keep them modest to avoid drowning out lexical match quality.
- For summary mode you can pass both `mode: "summary"` and a tag_policy; the provider will apply it before retrieval and again for any post-retrieval nudges.

## Suggested defaults and examples

- Primary care +0.6 to +1.0: helps when the question is general or longitudinal.
- Administrative −0.2 to −0.6: trims low-yield notes without hiding important content.
- Nursing −0.1 to −0.4: reduces dominance of high-frequency vitals-only notes.
- Mental health +0.3 when explicitly querying related content.
- Education +0.2 if counseling/education content is often requested.

## Pros and cons

Pros
- Improves early recall/precision for common clinical Q&A without expensive re-ranking.
- Lightweight and transparent (regexes + small weights); easy to iterate.
- Per-request overrides let the UI steer retrieval for different modes (Ask vs Summary) or user preferences.

Cons / Risks
- Title coverage: some sites have inconsistent national titles; fallbacks to local title may be noisy.
- False positives/negatives: regex-based tags may misclassify ambiguous titles.
- Drift over time: new titles appear; the TAGS map should be maintained.
- Overweighting risk: too-high boosts can hurt relevant matches from other categories.

## Operational guidance

- Start with conservative weights. Increase gradually if you see obviously relevant notes being pushed below top_k.
- Prefer small negative weights over hard filters for downranking. Avoid zeroing out entire categories unless there’s a clear requirement.
- Validate on real patients: compare top@12 with and without the override for representative queries.
- Monitor excerpt diversity: ensure the 3‑per‑note cap still yields a mix of sources.

## Debugging and observability

- For a given query, the model returns matches with note titles and dates in citations; check whether desired categories surface earlier as weights change.
- Consider logging the applied tag(s) and tag_boost per chunk during development to calibrate weights.

## API quick reference

- /api/query/ask: accepts `tag_policy` in body. Applies to both standard ask and when `mode: "summary"`.
- /api/query/rag_results: also accepts `tag_policy`; affects early note list.

That’s it—keep the weights small, iterate with real cases, and use per‑mode overrides to tailor behavior without impacting global defaults.
