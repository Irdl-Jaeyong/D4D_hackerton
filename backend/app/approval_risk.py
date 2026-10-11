"""Deterministic priority; no LLM inputs. Scenario presets are synthetic."""
import json
from pathlib import Path
CONFIG=json.loads((Path(__file__).resolve().parents[2]/'config/approval_risk.json').read_text())

def evaluate(signals,config=CONFIG):
    scores={k:signals.get(k) for k in ('S','U','A')}
    missing=[k for k,v in scores.items() if type(v) not in (int,float) or not 0<=v<=5]
    forced=[reason for flag,reason in config['p0_flags'].items() if signals.get(flag) is True]
    score=None if missing else sum(config['weights'][k]*v for k,v in scores.items())
    priority='P0' if forced else None if score is None else 'P1' if score>=config['thresholds']['P1'] else 'P2' if score>=config['thresholds']['P2'] else 'P3'
    return {'score':score,'priority':priority,'scores':scores,'missing':missing,
            'status':'unavailable' if missing else 'evaluated','p0_reasons':forced,
            'reason':signals.get('reason','S/U/A 입력에 따른 규칙 계산'),'source':'synthetic',
            'formula':'R = 10S + 6U + 4A'}

def sort_key(m):
    r=m['risk'];p=r['priority']
    return (int(p[1]) if p else 4,-(r['score'] if r['score'] is not None else -1),-m['created_at'],m['id'])
