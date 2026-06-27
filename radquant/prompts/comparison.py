"""radquant/prompts/comparison.py — prompts for longitudinal interval comparison."""

COMPARISON_SYSTEM = """\
You are an expert radiologist comparing two chest X-rays from the same patient.
Your task is interval analysis: identify what has changed between the prior study
and the current study. Be precise, concise, and ground every observation in
what is visually present. Do NOT invent findings.
"""

COMPARISON_USER = """\
IMAGE 1 (prior study, {prior_date}): the FIRST image provided.
IMAGE 2 (current study, {current_date}): the SECOND image provided.
Interval between studies: {interval}.

Classifier findings — Prior study:
{prior_findings_str}

Classifier findings — Current study:
{current_findings_str}

Compare the two images and classify every finding into one of five categories:
  new       — present in IMAGE 2 but absent in IMAGE 1
  worsened  — present in both; larger / denser / more extensive in IMAGE 2
  improved  — present in both; smaller / less dense in IMAGE 2
  resolved  — present in IMAGE 1 but absent in IMAGE 2
  stable    — present in both with no meaningful change

Then write a single-sentence clinical impression summarising the net interval change.

Respond ONLY with a valid JSON object — no preamble, no markdown fences:
{{
  "new":      [{{"finding": "...", "detail": "..."}}],
  "worsened": [{{"finding": "...", "detail": "..."}}],
  "improved": [{{"finding": "...", "detail": "..."}}],
  "resolved": [{{"finding": "...", "detail": "..."}}],
  "stable":   [{{"finding": "...", "detail": "..."}}],
  "impression": "..."
}}

If a category has no findings, use an empty list [].
"""

DRAFT_COMPARISON_ADDENDUM = """\

COMPARISON CONTEXT — prior study dated {prior_date} (interval: {interval}):
{comparison_impression}

Your FINDINGS section MUST include an "INTERVAL CHANGE" paragraph.
Begin that paragraph with: "Compared to prior study dated {prior_date}, ..."
List each changed finding explicitly (new, worsened, improved, resolved).
"""
