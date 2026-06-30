# Provenance Guard — Planning

## 1. Detection Signals

**Signal 1 — LLM Judgment (Groq, llama-3.3-70b-versatile)**
- What it measures: holistic semantic/stylistic coherence. We prompt the model to read the text and judge whether it reads as AI-generated or human-written, and to return a confidence score.
- Output format: a float 0–1, where 1.0 = strongly reads as AI-generated, 0.0 = strongly reads as human-written.
- What it can't capture: it has no access to ground truth, only "does this *sound like* typical AI output." Short texts, heavily edited AI text, or very formal human writing can fool it in either direction. It's also a black box — we can't inspect *why* it gave a score.

**Signal 2 — Stylometric Heuristics (pure Python)**
- What it measures: structural/statistical properties of the text — sentence length variance, type-token ratio (vocabulary diversity), average sentence length. AI text tends to be more uniform across these; human writing is more variable.
- Output format: a float 0–1, where 1.0 = high uniformity (reads as AI-like), 0.0 = high variability (reads as human-like). Computed by normalizing and combining the 3 sub-metrics.
- What it can't capture: causation. Uniformity is a *correlate* of AI text, not a guarantee — a terse human writer, a poem with repetition, or a non-native speaker writing carefully can all score as "uniform" without being AI-generated. It also can't see meaning at all, only structure.

**Why these two:** one is semantic (holistic judgment), one is structural (measurable statistics). They are independent — a text can fool one without fooling the other, which is exactly why combining them is more informative than either alone.

**Combining into one score:**
`combined_confidence = (0.6 * llm_score) + (0.4 * stylometric_score)`

We weight the LLM signal higher because it's more semantically aware, but the stylometric signal still meaningfully pulls the score when the two disagree — this is what creates "uncertain" results rather than one signal always dominating.

## 2. Uncertainty Representation

- A confidence score of **0.6** means: the combined signals lean slightly toward AI-generated, but not strongly enough to assert it. It should produce the "uncertain" label, not "likely AI."
- Raw signal outputs (each 0–1) are combined via the weighted average above — no additional calibration curve, given time constraints. This is a documented simplification (see Known Limitations in README).
- **Thresholds:**
  - `combined_confidence >= 0.75` → **Likely AI-generated**
  - `0.40 <= combined_confidence < 0.75` → **Uncertain**
  - `combined_confidence < 0.40` → **Likely human-written**

These thresholds are intentionally asymmetric-aware: because a false positive (calling a human's work AI) is worse than a false negative on a creative platform, the "Likely AI" band starts high (0.75) — we require strong agreement from both signals before asserting AI authorship. The "uncertain" band is wide (0.40–0.75) on purpose, to catch ambiguous cases rather than force a binary call.

## 3. Transparency Label Design

| Label Variant | Exact Text Shown to User |
|---|---|
| High-confidence AI | "This content shows strong signals of AI generation. Our system is fairly confident this was AI-written, but no detection method is perfect — if you believe this is incorrect, you can appeal this classification." |
| High-confidence Human | "This content shows strong signals of human authorship. Our system found no significant indicators of AI generation." |
| Uncertain | "We're not confident either way about this content's origin. The signals we use gave mixed or weak indicators. This label reflects genuine uncertainty, not a hidden verdict." |

## 4. Appeals Workflow

- **Who can appeal:** the original creator (identified by `creator_id`), using the `content_id` returned at submission time.
- **What they provide:** `content_id` and free-text `creator_reasoning` explaining why they believe the classification is wrong.
- **What the system does:** looks up the content_id, sets its status to `under_review`, and writes a new audit log entry containing the appeal reasoning plus a reference back to the original decision (signal scores, combined confidence, original label). No automated re-classification — a human reviewer would read the appeal_reasoning and original decision side by side.
- **What a reviewer would see:** in `/log` output, an entry with `status: under_review` and `appeal_reasoning` populated, sitting alongside the original `classified` entry for the same `content_id` — giving full context for a manual decision.

## 5. Anticipated Edge Cases

1. **Short, simple, repetitive creative text** (e.g., a children's poem or a minimalist piece using deliberate repetition) — stylometric heuristics will likely score this as uniform/AI-like, since low vocabulary diversity and short consistent sentence length are exactly what the heuristic looks for, even though this is a common deliberate human creative choice.
2. **Formal academic or technical human writing** (e.g., the borderline finance-text example) — both signals may lean AI: the LLM signal because formality reads as "generic," and stylometrics because careful, edited prose reduces sentence-length variance. This is our flagged false-positive risk scenario, and is exactly why the "uncertain" band exists rather than a hard cutoff at 0.5.

## Architecture

### Submission Flow
```
POST /submit {text, creator_id}
        |
        v
  [Flask: generate content_id]
        |
        v
  [Signal 1: Groq LLM] --> llm_score (0-1)
        |
        v
  [Signal 2: Stylometric heuristics] --> stylometric_score (0-1)
        |
        v
  [Confidence Scoring: weighted combine] --> combined_confidence
        |
        v
  [Label Generator: map score -> label text]
        |
        v
  [Audit Log: write entry (content_id, scores, label, timestamp)]
        |
        v
  Response: {content_id, attribution, confidence, label}
```

### Appeal Flow
```
POST /appeal {content_id, creator_reasoning}
        |
        v
  [Flask: look up content_id]
        |
        v
  [Update status -> "under_review"]
        |
        v
  [Audit Log: write appeal entry, linked to original decision]
        |
        v
  Response: {confirmation, content_id, status}
```

**Narrative:** A submission flows linearly through both detection signals before scoring and labeling happen — each signal is computed independently and only combined at the scoring step, so either signal can be debugged in isolation. An appeal is a separate, simpler flow: it doesn't re-run detection, it only updates status and logs the creator's reasoning next to the original decision for a human reviewer to compare.

## AI Tool Plan

**M3 (submission endpoint + first signal):**
- Sections provided to AI tool: Detection Signals (Signal 1 only) + Architecture diagram (submission flow).
- What I'll ask for: Flask app skeleton with `POST /submit` route stub, and the Groq-based signal 1 function.
- Verification: call the signal 1 function directly with 2-3 sample texts before wiring it into the route; check the output format matches spec (float 0-1).

**M4 (second signal + confidence scoring):**
- Sections provided: Detection Signals (both) + Uncertainty Representation + Architecture diagram.
- What I'll ask for: stylometric signal function, and the confidence-scoring function combining both signals per my weighting formula.
- Verification: run the 4 test inputs (clear AI, clear human, 2 borderline) and confirm scores land in the expected relative order; check the scoring function's thresholds match planning.md exactly, not an AI-invented approximation.

**M5 (production layer):**
- Sections provided: Transparency Label Design + Appeals Workflow + Architecture diagram.
- What I'll ask for: label-generation function mapping confidence to the 3 exact label strings, and the `POST /appeal` endpoint.
- Verification: submit inputs producing all 3 confidence bands and confirm exact label text matches planning.md; test an appeal with a real content_id and confirm `/log` shows `status: under_review` with reasoning populated.