# Business Value

The Ground Truth Curation Tool accelerates and simplifies how subject-matter experts (SMEs) create and maintain high-quality ground truth datasets. These datasets are the backbone for measuring accuracy of our agent solution.

## Why It Matters

- **Ground truth is the source of truth** for model and agent evaluation. Without it, accuracy claims are anecdotal and hard to defend.
- **SMEs' time is scarce**; streamlining their workflow enables broader, deeper coverage of business-critical scenarios.
- **Measurable accuracy**, grounded in curated truth, improves go/no-go decisions, roadmap prioritization, and customer trust.

## Value Pillars

### 1. Faster Curation
- Guided flows and inline validation reduce back-and-forth and rework
- Consolidated UI replaces ad-hoc spreadsheets and manual scripts

### 2. Higher Quality and Consistency
- Standardized tagging ensures comparable examples across teams
- Human review of synthetic questions ensures relevance and correctness

### 3. Broader Coverage of Critical Scenarios
- Targeted assignment and progress visibility help close coverage gaps
- Built-in sampling and prioritization align SME effort with business impact

### 4. Trustworthy Accuracy Measurement
- Ground truth enables repeatable offline evals and release gates

## Expected Outcomes

These are directional targets to validate as we roll out:

- **2–4x faster** SME curation cycles per example set
- **30–50% reduction** in review rework due to standardized templates and inline checks
- **2x increase** in covered business scenarios within priority domains
- **Objective release decisions** based on repeatable accuracy metrics tied to curated truth

## How Value Shows Up in Practice

- **Delivery**: Shorter cycle time on creating new ground truth to cover new areas of agent behavior
- **Quality**: Fewer regressions due to stable, versioned test sets and release gates
- **Adoption**: Clear accuracy deltas before/after changes drive stakeholder buy-in
- **Cost**: Reduced SME hours per curated example and less engineering support for ad-hoc pipelines

## Key Performance Indicators

### Curation Lead Time
- **Metric**: Time from assignment → approved ground truth
- **Targets**: Track median and p90 times

### Rework Rate
- **Metric**: % of examples requiring revision after review
- **Target**: <20% rework rate

### Coverage
- **Metric**: Number of scenarios, intents, or tags with ≥ N curated examples
- **Target**: 100% coverage of priority scenarios

## Next Steps

1. **Instrumentation**: Capture baseline metrics for current curation and evaluation flows
2. **Pilot rollout**: Onboard a small SME group in one priority domain; compare metrics to baseline
3. **Iterate**: Address usability feedback; tune templates, tags, and review flows
4. **Scale**: Expand to additional domains and SME teams; track KPIs over time
