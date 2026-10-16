"""Conservative, source-backed suggestions. Documents never create app accounts."""
import hashlib
import re

NAME = r"[A-Z][a-zA-Z'’-]+(?: [A-Z][a-zA-Z'’-]+){1,3}"
ROLES = r"Managing Director|Operations Director|Finance Manager|Chief Executive Officer|Chief Operating Officer|Chief Financial Officer|CEO|COO|CFO|Founder|Co-founder|Dispatch Manager|Fleet Manager|Warehouse Manager|Operations Manager|Project Manager|Procurement Lead|Account Manager|Delivery Supervisor|Rider Supervisor"


async def current_chunks(store):
    sources = {s['id']: s for s in await store.list('source', 10000) if not s.get('is_version')}
    return [c for c in await store.list('chunk', 10000)
            if c.get('active') and sources.get(c['source_id'], {}).get('active')
            and sources[c['source_id']].get('import_complete')
            and sources[c['source_id']]['version'] == c['version']]


def suggest_people(chunks):
    suggestions, seen = [], set()
    companies = {m[1].lower() for c in chunks for m in re.finditer(r"\b([A-Z][\w&'-]*(?: [A-Z][\w&'-]*){0,5}) Company Profile\b", c['excerpt'])}
    for chunk in chunks:
        text = chunk['excerpt']
        matches = []
        # Both table-style "Operations Director Ada Bello" and prose
        # "Ada Bello is the Operations Director" are supported.
        for match in re.finditer(rf"(?=\b({ROLES})\s*[:|–—-]?\s+({NAME}))", text):
            name = re.split(r"\s+(?:Managing|Operations|Finance|Head|Company|The|Owner|Services|Document)\b", match[2])[0]
            matches.append((name, match[1], text[match.start():match.start(2) + len(name)]))
        for match in re.finditer(rf"\b({NAME})\s+(?:is|serves as)\s+(?:the\s+)?({ROLES})\b", text):
            matches.append((match[1], match[2], match[0]))
        for match in re.finditer(rf"\b({NAME})\s+(owns|approves|monitors|supervises|coordinates|checks|manages)\s+([^.;!?\n]{{3,180}})", text):
            matches.append((match[1], '', match[0]))
        for name, role, quote in matches:
            name = re.sub(rf'^(?:{ROLES})\s+', '', name)
            if not re.fullmatch(NAME, name) or name.lower() in companies:
                continue
            key = (name.lower(), role.lower(), quote.lower())
            if key in seen:
                continue
            seen.add(key)
            ident = 'person_' + hashlib.sha256((chunk['id'] + quote).encode()).hexdigest()[:20]
            suggestions.append({'id': ident, 'name': name, 'role': role,
                                'responsibility': quote, 'quote': quote,
                                'evidence_ids': [chunk['id']], 'source_name': chunk['title'],
                                'location': chunk['location'], 'confirmed': False})
    grouped = {}
    for person in suggestions:
        key = person['name'].lower()
        if key not in grouped:
            grouped[key] = {**person}
            continue
        prior = grouped[key]
        if person['role'] and person['role'] not in prior['role'].split(' / '):
            prior['role'] = ' / '.join(filter(None, [prior['role'], person['role']]))
        if person['responsibility'] not in prior['responsibility']:
            prior['responsibility'] = (prior['responsibility'] + '\n' + person['responsibility'])[:2000]
        prior['evidence_ids'] = list(dict.fromkeys(prior['evidence_ids'] + person['evidence_ids']))
    for person in grouped.values():
        person['id'] = 'person_' + hashlib.sha256((person['name'].lower() + '|'.join(sorted(person['evidence_ids']))).encode()).hexdigest()[:20]
    return sorted(grouped.values(), key=lambda p: p['name'])[:60]


def quick_answer(query, evidence):
    """Only explicit, narrowly matched facts can bypass generation."""
    q = query.lower().strip(' ?.!')
    if re.search(r'\b(founder|founded by|who founded)\b', q):
        # Absence is scoped to the checked evidence, not asserted as a fact
        # about the company. A year and director are never substituted.
        if not any(re.search(r'\b(founder|founded by|established by)\b', e['excerpt'], re.I) for e in evidence):
            return {'answer': "The documents I checked do not name the founder. A founding year or Managing Director is not enough to identify that person. Add a company history or founder profile to answer this.", 'claims': []}
    if re.search(r'\b(name of (?:the |my |our )?company|company(?:\'s)? name|what is (?:the |my |our )?company called)\b', q):
        for e in evidence:
            match = re.search(r"\b([A-Z][\w&'-]*(?: [A-Z][\w&'-]*){0,5}) Company Profile\b", e['excerpt'])
            if match:
                text = 'The company is ' + match[1] + '.'
                return {'answer': text, 'claims': [{'text': text, 'evidence_ids': [e['id']]}]}
    if re.match(r'^(?:who is|who\'s|who are|who is responsible for)\b', q):
        role = next((role for role in ROLES.split('|') if role.lower() in q), None)
        if not role and re.search(r'\bresponsible for operations\b', q):
            role = 'Operations Director'
        if role:
            people = [p for p in suggest_people(evidence) if role.lower() in p['role'].lower().split(' / ')]
            if len(people) == 1:
                person = people[0]
                text = person['name'] + ' is listed as ' + role + '.'
                return {'answer': text, 'claims': [{'text': text, 'evidence_ids': person['evidence_ids']}]}
    if re.search(r'\bwhat (?:does|do) (?:our|my|the) company do\b', q):
        for e in evidence:
            title = re.search(r"\b([A-Z][\w&'-]*(?: [A-Z][\w&'-]*){0,5}) Company Profile\b", e['excerpt'])
            if title:
                sentence = re.search(re.escape(title[1]) + r' (?:manages|provides|offers|delivers|builds|makes|operates)\b[^.!?]{5,650}[.!?]', e['excerpt'])
                if sentence:
                    text = sentence[0]
                    return {'answer': text, 'claims': [{'text': text, 'evidence_ids': [e['id']]}]}
    return None


def draft_profile(chunks):
    description = quick_answer('what does our company do?', chunks)
    people = suggest_people(chunks)
    facts = list(description['claims']) if description else []
    facts.extend({'text': p['responsibility'], 'evidence_ids': p['evidence_ids']} for p in people)
    return {'facts': facts[:12], 'draft': {
        'description': description['answer'] if description else '',
        'responsibilities': '\n\n'.join(p['name'] + (': ' + p['role'] if p['role'] else '') + '\n' + p['responsibility'] for p in people)[:10000],
        'evidence_ids': list(dict.fromkeys(i for fact in facts for i in fact['evidence_ids']))[:50]},
        'provider': 'source extraction', 'status': 'requires_confirmation'}
