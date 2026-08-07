# 브레인스토밍: AV 윤리에 대한 새로운 아이디어
# Brainstorm — Novel Ideas for Autonomous Vehicle Ethics (Korea-focused)

Moral Machine froze the debate at "who do you kill." That framing is useful
for eliciting raw preference data, but it's a poor model of how real AV
stacks make decisions (probabilistic risk, not certain death; continuous
control, not binary swerve) and it captures *what* people choose without
*why*. Below are extensions worth prototyping next, roughly ordered by how
directly they build on what's already in this repo.

## 1. Replace binary death with probabilistic harm
Real AVs reason in injury-probability distributions, not certain-death
trolley switches. Next version of `scenario_engine.py` could output a
**harm distribution** per path (e.g. "72% minor injury / 20% serious / 8%
fatal") instead of "this group dies." This lets us study **risk-tolerance
framing** — do people treat "small chance of death to many" differently
from "certain death to few," even at equal expected harm? That's a distinct,
measurable bias the classic Moral Machine can't isolate.

## 2. Reason-first, not choice-first
Currently we ask "why" *after* the click, so the free text tends to
rationalize the click. A second mode could ask people to **argue for both
sides before choosing** (steelman A, steelman B, then decide). Comparing
NLP-extracted value-frames from the pre-choice reasoning vs. the post-choice
justification is itself a research question: do stated principles predict
the choice, or does the choice retroactively pick the principle? That gap is
publishable on its own.

## 3. Korean-specific fault lines the original Moral Machine misses
Already seeded in `scenario_engine.py` as character types — worth deepening
with dedicated scenario *sets*, not just characters:
- **배달 라이더 (delivery riders):** Korea has unusually high delivery-rider
  traffic-death rates. A scenario cluster that varies rider visibility,
  helmet use, and time pressure could surface whether respondents implicitly
  blame riders for the job's own risk profile ("그들의 일이니까 어쩔 수 없다").
- **고령화 사회 (aging society):** Korea's elderly-pedestrian fatality rate
  is among the highest in the OECD. Test whether age-based prioritization
  shifts once respondents are told this statistic first (does information
  move stated ethics, or is the preference stable?).
- **이주노동자·다문화가정 (migrants, multicultural families):** a values
  frame the global Moral Machine dataset structurally can't measure well.
  Track `social_inclusion` tag rate and sentiment separately by respondent
  region/age (already collected at registration) to see if in-group bias
  correlates with demographics.
- **무단횡단 및 준법의식 (jaywalking / legalism):** Korea's culture leans
  legalistic — test whether "the pedestrian broke the law" *reverses* the
  save-preference even when the law-breaker is more vulnerable (e.g. a
  jaywalking elderly person vs. a law-abiding adult).

## 4. Deliberation mode instead of single-click mode
Add a **"AV policy jury"** flow: 5–7 respondents see the same scenario
sequence, discuss briefly (or answer async), and the app rolls up individual
choices *and* individual free-text reasoning into a rationale for the group
consensus. This gets closer to how AV ethics policy actually needs to be
set — not one person's snap judgment, but a legible group rationale a
regulator or manufacturer could point to.

## 5. Counterfactual "show me the AV's logic" screen
After N scenarios, show the respondent a **plain-language policy statement**
generated from their own choices ("당신의 선택 패턴은 대체로 '나이가 어릴수록
우선한다'는 원칙과 68% 일치합니다") and let them react: agree / this
overstates my view / this understates my view. That reaction is itself new
NLP-able data — it measures whether people *recognize their own revealed
preferences* as their actual values, a genuinely under-studied question in
AV ethics research.

## 6. Context-conditioned rather than global preferences
Moral Machine (and this app's v1 `results.html`) reports one global weight
per characteristic. A more useful signal for engineers: does the age
preference *change* in a school zone vs. a highway shoulder vs. a market
alley? `compute_preference_weights()` already has `scenario["context"]`
available — extend it to a context × tag matrix, not a flat tag average.
This is the single highest-value near-term upgrade: it's the difference
between "Koreans prefer to save children" (weak, decontextualized) and
"Koreans prefer to save children specifically in school-zone contexts, but
not elsewhere" (an actual, usable design input for AV behavior policy).

## 7. Explainability feedback loop for actual AV systems
Long-horizon idea: package the aggregated, anonymized value-frame weights as
a versioned **JSON "ethics config"** (`/api/insights` already returns
close to this shape) that a simulated AV planner could consume as a
tie-breaking prior when its own risk model is genuinely indifferent between
two paths. This doesn't mean "crowd-sourced trolley votes control real
cars" (ethically fraught and not this project's claim) — it means the
platform produces a structured, falsifiable artifact that AV policy teams
and regulators can audit, critique, and version, instead of an opaque
in-house ethics call.

## 8. Cross-cultural comparison mode
Since the scenario engine is data-driven (character list + context list),
a second character/context pack (e.g. "generic Moral Machine" characters)
could run in parallel, letting the platform report **Korea vs. global
baseline deltas** on the same dilemma shapes — turning this from a
standalone dataset into a comparative one, which is where the actual
research/publication value tends to concentrate.

---
### Suggested build order
1. Context × tag matrix for results (#6) — cheap, high signal, extends
   existing code paths only.
2. Probabilistic harm framing (#1) — changes `scenario_engine.py` output
   shape and `judge.html` copy, no new infra.
3. Post-choice "does this match you?" screen (#5) — new template + one
   new table, reuses NLP pipeline.
4. Deliberation / jury mode (#4) and cross-cultural mode (#8) — larger,
   do these once the core loop has real usage data.
