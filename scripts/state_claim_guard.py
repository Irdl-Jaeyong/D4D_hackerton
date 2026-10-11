"""Conservative unsupported-state filter; rejection is preferable to invented status."""
import re

def check(text,vehicles):
    if not vehicles:
        if re.search(r'고장|정비|충전|수행불가',text):raise ValueError('no vehicle evidence for state claim')
        return
    facts=' '.join(str(v.get('fault') or '')+' '+str(v.get('readiness') or {}) for v in vehicles)
    claims=[(r'정비\s*중',r'정비'),(r'충전\s*중',r'충전'),(r'고장(?:으로|이|이 발생| 등록|으로 등록)',r'고장'),(r'수행불가(?: 상태|로 판정)',r'unavailable')]
    for claim,evidence in claims:
        if re.search(claim,text) and not re.search(evidence,facts):raise ValueError('unsupported state claim')
    if re.search(r'재개 가능|바로 출동|즉시 재개',text):raise ValueError('unverified operational clearance')
