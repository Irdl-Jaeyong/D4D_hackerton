"""Export review candidates; excludes engine allocations and unverified numeric claims."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SYSTEM='한국어로 질문에 바로 답한다. 판정 근거와 실제 원인을 구분하고 모르는 정보는 질문한다. 상태 질문은 설명 하나, 안전 검토 요청은 세 가지 검토안. 명령 실행이나 승인을 주장하지 않는다.'
def build():
 rows=[]
 for path in [ROOT/'config/web_faq_60.json',ROOT/'config/chat_safety_cases_20.json']:
  data=json.loads(path.read_text());items=data['faqs'] if isinstance(data,dict) else data
  topics={r['id']:r for r in data.get('topics',[])} if isinstance(data,dict) else {}
  for item in items:
   if 'topic_id' in item:
    topic=topics[item['topic_id']];fact=topic['source_fact'];source=topic['source'];check=item['clarifying_question']
   else:fact='이 상황만으로 고장 원인을 확정할 수 없습니다.';source=item['source'];check=item['check']+'을 알려주세요.'
   rows.append({'id':item['id'],'source':source,'review_status':'needs_human_review','messages':[{'role':'system','content':SYSTEM},{'role':'user','content':item['question']},{'role':'assistant','content':fact+' '+check}]})
 out=ROOT/'config/training/dialogue_candidates.jsonl';out.parent.mkdir(exist_ok=True);out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 (out.parent/'dialogue_manifest.json').write_text(json.dumps({'candidate_count':len(rows),'weight_training_performed':False,'review_required':True,'excluded':'기체 배정·전술 기동·검증되지 않은 수치·중복 원문은 학습 입력에서 제외','runtime':'검색된 참고 사실과 소수의 대화 형식 예시를 LLM에 전달'},ensure_ascii=False,indent=2)+'\n')
 return len(rows)
if __name__=='__main__':print(build())
