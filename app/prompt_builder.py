"""Offline visual rules. Custom phrase mappings take precedence over built-in rules."""
import re
NEGATIVE = 'text, watermark, logo, blurry, low quality, distorted face, extra fingers, bad anatomy, duplicated objects, (illustration:1.5), (cartoon:1.5), (vector art:1.5), drawing, painting, abstract shapes, product photography, still life'
STYLE = '(realistic DSLR photo:1.3), clean composition, natural lighting, realistic skin texture. '


def build(sentence: str, phrase: str, overrides: dict[str, str] | None = None) -> tuple[str, str]:
    text = sentence.lower()
    custom = (overrides or {}).get(phrase)
    if custom:
        scene = custom
    elif 'abstain' in text and 'alcohol' in text:
        scene = '(A doctor and a male patient sitting face to face:1.4) in a clinic. Two people, doctor in a white coat on the left, patient in a blue shirt on the right refusing a small wineglass with an open palm gesture. Waist-up view of both people.'
    elif 'abstain' in text and ('vot' in text or 'ballot' in text):
        scene = '(Five adults sitting around a conference table:1.3). Three committee members keep their hands lowered, two other members raise one hand to vote. Plain meeting room, clearly visible faces and upper bodies, candid meeting photograph.'
    elif 'inaugural' in text and ('address' in text or 'speech' in text):
        scene = '(A candid event photograph of a man speaking at a plain podium:1.5). An anonymous actor in a dark suit portrays a fictional newly elected president during an inaugural address. Realistic human face and skin, softly blurred seated audience, neutral indoor hall.'
    elif 'vot' in text or 'ballot' in text or 'election' in text:
        scene = 'A fictional civic voting scene. Anonymous people place blank folded ballots into a plain ballot box in a neutral meeting room.'
    elif any(term in text for term in ('president', 'inaugur', 'politic', 'minister')):
        scene = 'A fictional official meeting. An anonymous public official discusses plans with colleagues around a plain conference table, using gestures and blank documents.'
    elif 'apolog' in text:
        scene = 'Two people facing one another. One person makes an apologetic gesture with a lowered head, while the other listens calmly.'
    elif 'agree' in text and 'disagree' not in text:
        scene = 'Colleagues at a meeting table nod and shake hands in agreement, with relaxed expressions and blank documents.'
    else:
        # Conservative fallback: keep the actors and action, discard common abstract wrappers.
        scene = sentence.strip().rstrip('.')
        replacements = {'decided to ': '', 'chose to ': '', 'in order to ': 'to ',
                        'is planning to ': 'is preparing to ', 'realized that ': 'observes that '}
        for old, new in replacements.items():
            scene = scene.replace(old, new)
        # Render a keyword/action fragment rather than quote the learning sentence.
        scene = re.sub(r'\b(The|the|A|a|An|an)\s+', '', scene)
        scene = re.split(r'\b(?:because|although|which)\b', scene, maxsplit=1)[0].strip(' ,')
        scene = 'Visual focus: ' + scene + '. One clear scene, visible gestures and concrete surroundings.'
    political = any(term in text for term in ('president', 'inaugur', 'ballot', 'voting', 'election', 'politic', 'minister'))
    if political:
        scene += ' Generic fictional setting with invented people, no resemblance to real political figures, no party symbols or recognizable national emblems.'
    return STYLE + scene.strip() + ' No text in image.', NEGATIVE + ', captions, subtitles, letters, signage'
