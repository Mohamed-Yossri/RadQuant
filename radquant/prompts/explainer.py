"""radquant/prompts/explainer.py — prompts for patient-friendly report translation."""

EXPLAINER_PROMPT = """\
You are a patient educator. A radiologist has written the following medical report.
Translate it into plain, friendly language that a patient with no medical background
can understand. 

Rules:
- Do NOT copy the original wording. Replace each medical term with everyday words.
- Preserve the clinical meaning and severity accurately.
- If something is normal, say so reassuringly.
- If something needs follow-up, say so clearly but without causing undue alarm.
- Keep the tone warm and clear.
- After your plain-language translation, add a GLOSSARY section listing any
  medical terms from the original with a one-sentence plain-English definition.
  Format: GLOSSARY:\n- term: definition

Original report:
{report}
"""

GLOSSARY_PARSE_HINT = "GLOSSARY:"
