"""Conservative backstop for explicit visual instructions in generated questions."""
import re


def requires_drawing(question: str) -> bool:
    if re.search(r'\bdraw\s+conclusions\b', question, re.I):
        return False
    instruction = r'(?:^|[.!?:,;]\s+)(?:please\s+)?(?:draw|sketch|plot|annotate|construct|illustrate|label)\b'
    visual = r'.{0,100}\b(?:diagram|graph|circuit|structure|curve|vector|forces?|cell|molecule|shape|tree|network|ray|path|axes|field|distribution|construction|schematic|flowchart)\b'
    return bool(re.search(instruction + visual, question, re.I) or re.search(
        r'^\s*(?:plot|sketch)\s+.*(?:=|\bfunction\b)', question, re.I))


def normalize_requirement(item):
    if requires_drawing(item.question):
        item.drawing_required = True
    if item.drawing_required:
        # A model-generated brief can accidentally reveal the reference solution.
        # Only show a neutral instruction before the learner has attempted it.
        item.drawing_prompt = 'Create the visual answer requested in the question. Include clear labels, directions and units where relevant.'
    else:
        item.drawing_prompt = ''
