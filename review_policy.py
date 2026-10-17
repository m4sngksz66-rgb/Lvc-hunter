"""Conservative notification policy: distinguish candidates from proven bargains.

No seller description is treated as independent proof of factory, age or condition.
"""

def decide(score, threshold, tier_confidence, condition_info, deal, model_key='', shipping_known=False):
    reasons=[]
    if score < threshold:
        return 'ignore', ['low_visual_score']
    reasons.append('visual_candidate')
    if tier_confidence != 'verified':
        reasons.append('identity_not_verified')
    if condition_info['condition_evidence'] != 'verified':
        reasons.append('condition_not_verified')
    if not model_key:
        reasons.append('exact_model_missing')
    if not shipping_known:
        reasons.append('shipping_unknown')
    if deal['deal_status'] != 'potential_bargain':
        reasons.append('price_' + deal['deal_status'])
    if not any(x in reasons for x in ('identity_not_verified','condition_not_verified','exact_model_missing','shipping_unknown')) and deal['deal_status']=='potential_bargain':
        return 'bargain_alert', reasons
    return 'manual_review', reasons
