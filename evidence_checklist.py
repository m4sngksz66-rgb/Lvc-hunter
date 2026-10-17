"""Explain which photos/evidence would allow a candidate to be verified."""
import re

def checklist(title='', description='', tier='unclassified', condition='unknown', tier_confidence='inferred', condition_evidence='unknown'):
    s=f'{title} {description}'.lower()
    tasks=[]
    if tier_confidence!='verified':
        tasks.append('Närbild på knappens baksida med läsbar fabrikskod (exempelvis 555)')
        tasks.append('Närbilder på invändiga etiketter: modell, tillverkningsland och eventuell datumkod')
    if tier in ('lvc_valencia_555','true_vintage','unclassified'):
        tasks.append('Närbilder på bakfickor, sömmar, nitar och selvedge-kant')
    if condition_evidence!='verified':
        tasks.append('Bilder på slitage, fållar, knän och gren för skickbedömning')
        if condition in ('unwashed','nos','nwt','nwot') or re.search(r'\b(?:unwashed|otvättad|nos|nwt|nwot)\b',s):
            tasks.append('Oberoende stöd för påstått oanvänt/otvättat skick; bilder kan sällan bevisa detta ensamma')
    tasks.append('Exakt modell, storlek, totalpris inklusive frakt och jämförbara avslutade försäljningar')
    return list(dict.fromkeys(tasks))
