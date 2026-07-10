# Agent Operating Contract

This file defines the rules every AI coding agent must follow when contributing to this repository.
Read this file in full before touching any other file.

---

## Project Identity

This is a reproducible, configuration-driven data engineering and analytics pipeline built on top of
publicly available Inside Airbnb snapshot data. The primary analytical case is Amsterdam. A second
city may be added later as a configuration-only extension.

The project is scoped to a local Python stack: pandas, DuckDB, Parquet, SciPy, statsmodels, and
scikit-learn. No cloud infrastructure, orchestration framework, or distributed system is used.

---

## Before You Touch Any File

1. Read the full repository structure so you understand what already exists.
2. Read any file you are about to modify. Do not infer contents from the filename alone.
3. Inspect the actual downloaded schema before writing any transformation. Never invent column names.
4. If a requirement is ambiguous, choose the smallest defensible interpretation and record it in
   `docs/assumptions.md`.

---

## Scope Discipline

Work only inside the scope that was explicitly requested. Do not add optional features, bonus
components, or "nice to have" helpers unless they were asked for by name. Do not start the next
logical step until the current one is verified and reported.

---

## Code Quality Rules

These rules are non-negotiable. A pull that violates them will be rejected regardless of whether it
runs.

### Structure

- Keep all reusable logic inside `src/airbnb_intelligence/`. Do not duplicate pipeline logic in
  notebooks.
- Notebooks are narrative views that import and call tested functions from `src`. They do not
  re-implement transformations.
- Keep functions short and single-purpose. A function that does two independent things should be two
  functions.
- Use type hints on every public function signature.
- Use named constants for column names and validation thresholds rather than repeating string
  literals throughout the codebase.

### Simplicity

- Use the simplest design that satisfies the current requirement.
- Do not create generic base classes, abstract factories, dependency injection containers, service
  locators, repository layers, or plugin registries unless a concrete current need exists and the
  abstraction is the simplest way to meet it.
- Do not add speculative helpers, utility modules, or compatibility shims without a concrete caller
  already in the codebase.
- Do not add unnecessary `if/else` branches, fallback chains, or retry layers. Add a branch only
  when it represents a real data rule, a real validation rule, or a required failure state.
- Prefer one direct implementation path with explicit inputs and outputs over a clever multi-path
  design that tries to recover silently from programmer errors.

### Data integrity

- Do not silently drop rows. Every excluded row must appear in the quarantine table with a source
  row identifier and a reason string.
- Do not silently impute, rename, or transform data. Every material decision must be documented in
  `docs/assumptions.md` or `docs/decision_log.md`.
- Preserve original values alongside derived values so lineage remains traceable.
- Do not hard-code absolute paths, machine-specific settings, credentials, or secrets anywhere in
  the codebase.
- Use explicit failure for invalid configuration and invalid data contracts. Log the reason,
  preserve the evidence, and stop or quarantine as the pipeline step contract requires.

### Comments and documentation

- Do not add comments to obvious Python statements. Comment only non-obvious business logic, data
  interpretation choices, statistical assumptions, or deliberate trade-offs.
- Do not leave placeholder comments, TODO markers, or dead code in submitted work.
- Remove unused imports, unused variables, and unused dependencies before reporting completion.

### Testing

- Add tests for every new public function that has a meaningful failure state.
- Use small local fixtures in tests. Do not depend on the real downloaded dataset in unit tests.
- Tests must be deterministic and must not require network access.

---

## Analytics Rules

These rules protect the integrity of every analytical claim in the report.

- Do not describe availability as occupancy. Availability rate and occupancy proxy are different
  concepts; use the correct label and add a definition footnote every time the proxy is used.
- Do not describe calendar-derived revenue estimates as observed revenue. Label them as revenue
  proxy and document the formula.
- Do not describe regression coefficients as causal effects. Coefficients are associations in an
  observational dataset.
- Do not report p-values without effect sizes and confidence intervals.
- Do not use statistical significance as the sole conclusion of any hypothesis test.
- Apply Benjamini-Hochberg false-discovery-rate correction across all planned hypotheses as the
  primary multiple-testing adjustment. Report Bonferroni as a conservative sensitivity check.
- Use log price as the target for price comparisons and regression when price distributions are
  heavily right-skewed. State the transformation in every caption and table note.
- Check and report test assumptions before interpreting results. If an assumption is violated,
  use a non-parametric sensitivity analysis.
- Do not introduce external event data unless it is available in the same snapshot and its join
  coverage is documented.

---

## Documentation Rules

- `docs/assumptions.md` records every assumption made about ambiguous fields, data quality
  decisions, and analytical choices. Add an entry whenever a decision is made.
- `docs/decision_log.md` records every significant engineering and architectural decision: options
  considered, reason for the choice, and trade-offs accepted.
- `docs/lineage.md` contains one entry per output table or Parquet dataset: source file(s), key
  transformations, filters or exclusions, output grain, primary key, foreign keys, and consuming
  SQL, chart, or model.
- `docs/ai_usage_disclosure.md` is updated continuously. Every AI tool, model version, assisted
  section, key prompt, validation step, and rejected suggestion must be recorded.

---

## Reporting Rules

- Do not invent numbers, findings, citations, or business recommendations.
- Every numeric claim in the report must trace back to a generated result table or SQL query.
- For each finding, include the population, snapshot date, method, result, caveat, and business
  interpretation.
- Clearly distinguish observed values, derived values, proxy measures, predictive outputs, and
  causal claims in every sentence that makes an analytical assertion.

---

## Security and Submission Rules

- Do not commit raw datasets, generated DuckDB files, virtual environments, or `.env` files.
- Do not commit personal information, API keys, tokens, passwords, or private email content.
- Confirm that `.gitignore` covers `data/raw/`, `data/staged/`, `data/processed/`, `db/`,
  `__pycache__/`, `.venv/`, and any secrets file before every commit.

---

## Reporting Completion

After completing any unit of work, report:

1. Files changed and the nature of each change.
2. Commands run and their output or exit status.
3. Test results: number passed, number failed, any skipped.
4. Assumptions added to `docs/assumptions.md`.
5. Any manual action still required from the developer.

Do not claim a result was verified unless the command actually ran successfully in this session.

---

## Prohibited Actions

- Do not commit any file in `data/raw/`, `data/staged/`, `data/processed/`, or `db/`.
- Do not run shell commands inside the pipeline code. Use Python standard library and pathlib.
- Do not use orchestration frameworks (Airflow, Prefect, Luigi) in the current scope.
- Do not add Spark, Kubernetes, or cloud SDK dependencies in the current scope.
- Do not submit code that cannot be explained line-by-line in a technical interview.
