"""Separate garment condition claims from seller knowledge. Claims are not verification."""
import re

PATTERNS = {
 'nwt': r'(?<!\w)nwt(?!\w)|\bnew with tags?\b|\bnya? med (?:etikett|lappar)\b',
 'nwot': r'(?<!\w)nwot(?!\w)|\bnew without tags?\b|\bnya? utan (?:etikett|lappar)\b',
 'nos': r'(?<!\w)nos(?!\w)|\bnew old stock\b|\bdeadstock\b',
 'unwashed': r'\bunwashed\b|\bunworn and unwashed\b|\bnever washed\b|\botvättad(?:e|t)?\b|\baldrig tvättad(?:e|t)?\b',
 'raw': r'\braw denim\b|\bdry denim\b|\boprewashed\b',
 'valencia': r'\bvalencia(?: street| st)?\b|\b(?:button|factory)\s*(?:stamp|code)?\s*555\b|\b555\s*(?:button|stamp|factory)\b|\b555.stämp(?:el|lad)\b',
}
SOPHISTICATED = r'\b(?:selvedge|selvage|redline|big e|single stitch|chainstitch|hidden rivets?|vintage clothing|lvc|valencia|deadstock|new old stock|nwt|nwot|nos|shrink.to.fit)\b'

def analyze_condition(title='', description='', verified_condition=None):
    s=(str(title or '')+' '+str(description or '')).lower()
    signals=[key for key,pattern in PATTERNS.items() if re.search(pattern,s,re.I)]
    if verified_condition in ('nwt','nwot','nos','unwashed','used'):
        condition=verified_condition
        evidence='verified'
    else:
        condition=next((k for k in ('nos','nwt','nwot','unwashed') if k in signals),'unknown')
        evidence='seller_claim' if condition!='unknown' else 'unknown'
    seller_knowledge='likely_informed' if re.search(SOPHISTICATED,s,re.I) else 'unknown'
    return {'condition':condition,'condition_evidence':evidence,'condition_signals':signals,
            'seller_knowledge':seller_knowledge}

def valencia_unwashed_priority(tier, tier_confidence, condition_info):
    """High-priority verified combination; claims alone only warrant manual verification."""
    if tier!='lvc_valencia_555':return 'none'
    if condition_info['condition'] not in ('unwashed','nos','nwt','nwot'):return 'none'
    if tier_confidence=='verified' and condition_info['condition_evidence']=='verified':return 'verified_priority'
    return 'verify_photos'
