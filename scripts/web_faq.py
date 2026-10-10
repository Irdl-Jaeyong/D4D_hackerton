"""Read-only FAQ retrieval; sourced facts separated from application options."""
import json,re
from functools import lru_cache
from pathlib import Path
from scenario_questions import normalized,grams
DATA=json.loads((Path(__file__).resolve().parents[1]/'config/web_faq_60.json').read_text())
TOPICS={row['id']:row for row in DATA['topics']}
def retrieve_faq(question):
    if re.search(r'(?<![A-Z0-9])(?:UAV|USV)-\d{2}(?!\d)',question,re.I):return None
    q=normalized(question);g=grams(question)
    ranks=[]
    for row in DATA['faqs']:
        rg=grams(row['question']);score=2*len(g&rg)/max(1,len(g)+len(rg))
        if q==normalized(row['question']):score=1
        ranks.append((score,row['id'],row))
    ranks.sort(key=lambda r:(-r[0],r[1]))
    return ranks[0][2] if ranks[0][0]>=.8 else None

def briefing(row,snapshot):
    topic=TOPICS[row['topic_id']];plans=[]
    for answer in row['answers']:
        plans.append({**answer,'formations':{g:snapshot['formations'][g] for g in ('usv','uav')},'tasks':[],
          'available':True,'requests':{'uav':0,'usv':0},'benefit':answer['action'],'unavailable_reason':'',
          'validation':'문서 기반 일반 질문. 기체 이동 계획 없음.','execution_scope':'검토 제안만; 승인·이동 없음.'})
    return {'summary':f"질문: {row['question']}\n공식 문서에서 확인한 내용: {topic['source_fact']}\n세 답변은 우리 프로젝트의 검토 제안입니다.",
      'scenario':None,'candidates':[],'retrieval_method':'web_document_faq','plans':plans,'catalog_count':200,
      'clarification_questions':[],'clarification_context':None,'reported_details':None,'faq_reference':row['id'],
      'web_sources':[topic['source']],'faq_check_question':row['clarifying_question'],'faq_situation_examples':examples_for_faq(row['id'],row['question'])}

@lru_cache(maxsize=1)
def situation_examples():
    path=Path(__file__).resolve().parents[1]/'config/faq_situations_deduplicated.jsonl'
    if not path.exists():path=path.with_name('faq_situations_600.jsonl')
    grouped={}
    if path.exists():
        for line in path.read_text().splitlines():
            row=json.loads(line)
            ids={q['faq_id'] for q in row.get('question_variants',[])} or {row['faq_id']}
            for id in ids:grouped.setdefault(id,[]).append(row)
    return grouped

def examples_for_faq(id,question):
    rows=situation_examples().get(id,[]);q=grams(question)
    ranked=sorted(rows,key=lambda row:-len(q&grams(row['condition']+' '+row['situation'])))
    return [{'synthetic':True,'condition':row['condition'],'sample_report':row['situation'],
             'sample_clarification':row['clarifying_question'],'response_perspectives':row['answers'],
             'limits':'답변 작성 참고용 합성 예시. 예시의 기체·잔량·시간·상태를 현재 사실로 사용하지 않음.'} for row in ranked[:1]]
