#!/usr/bin/env python3
"""Conservative exact behavioral deduplication, retaining numeric/state changes."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read_rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def stable(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def chat_key(row):
    # Never collapse distinct card semantics, geometry, fleet states or engine results.
    return stable({k:row[k] for k in ('scenario_id','snapshot','reported_target','expected_recommendations','checks')})
def faq_key(row):
    return stable({k:row[k] for k in ('topic_id','condition','situation','answers','source_reference')})
def deduplicate(rows,key,alias):
    groups={}
    for row in rows:
        signature=key(row)
        if signature not in groups:
            kept=copy.deepcopy(row);kept['source_ids']=[];kept['question_variants']=[];groups[signature]=kept
        kept=groups[signature];kept['source_ids'].append(row['id'])
        item=alias(row)
        if item not in kept['question_variants']:kept['question_variants'].append(item)
    return list(groups.values())
def write_rows(path,rows):path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
def run():
    chat=read_rows(ROOT/'config/chat_examples_1800.jsonl');faq=read_rows(ROOT/'config/faq_situations_600.jsonl')
    cleaned_chat=deduplicate(chat,chat_key,lambda r:{'source_id':r['id'],'question':r['messages'][1]['content'],'followup':r['messages'][3]['content']})
    cleaned_faq=deduplicate(faq,faq_key,lambda r:{'source_id':r['id'],'faq_id':r['faq_id'],'question':r['user_question']})
    write_rows(ROOT/'config/chat_examples_deduplicated.jsonl',cleaned_chat)
    write_rows(ROOT/'config/faq_situations_deduplicated.jsonl',cleaned_faq)
    # Review corpus, not an automatically trainable/chat-format fine-tune file.
    base_faq=json.loads((ROOT/'config/web_faq_60.json').read_text())['faqs']
    review=[{'kind':'scenario_dialogue','record':r} for r in cleaned_chat]+[{'kind':'faq_situation','record':r} for r in cleaned_faq]+[{'kind':'web_faq','record':r} for r in base_faq]
    write_rows(ROOT/'config/training_review_deduplicated.jsonl',review)
    before=5400+6000+180;after=len(cleaned_chat)*3+len(cleaned_faq)*10+len(base_faq)*3
    report={'policy':'exact behavioral equality; preserve numeric targets, all snapshot states, scenario identity, engine results and question aliases',
      'chat':{'before':len(chat),'after':len(cleaned_chat),'removed':len(chat)-len(cleaned_chat)},
      'faq_situations':{'before':len(faq),'after':len(cleaned_faq),'removed':len(faq)-len(cleaned_faq)},
      'base_faq_retained':len(base_faq),'review_records':len(review),'stored_answer_blocks_before':before,'stored_answer_blocks_after':after,
      'source_answer_blocks_not_repeated':before-after,'source_files_preserved':True,
      'limitations':['의미가 비슷해도 조건이나 결과가 다르면 합치지 않습니다.','공통 문구는 남아 있습니다. 전문가 검토·모델 학습·평가는 아직 진행하지 않았습니다.']}
    (ROOT/'config/deduplication_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (ROOT/'outputs/deduplication_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    text=['중복 정리 결과',f'상황 대화: {len(chat)} → {len(cleaned_chat)}',f'FAQ 상황: {len(faq)} → {len(cleaned_faq)}',f'기본 FAQ: {len(base_faq)}개 보존',f'중복 저장을 줄인 답변: {before} → {after}','숫자·위치·가용 상태·엔진 결과가 같을 때만 통합. 다른 질문 표현은 question_variants에 보존.','원본은 유지하고 정리본을 AI 참고 자료로 사용.','']
    for row in cleaned_chat:
        text.extend([row['id']+' | 원문 '+str(len(row['source_ids']))+'개 통합',row['messages'][1]['content'],row['messages'][-1]['content'],''])
    for row in cleaned_faq:
        text.extend([row['id']+' | 원문 '+str(len(row['source_ids']))+'개 통합',row['user_question']])
        text.extend(str(i)+'. '+a['title']+': '+a['action']+' 한계: '+a['limit'] for i,a in enumerate(row['answers'],1));text.append('')
    (ROOT/'outputs/training_review_deduplicated.txt').write_text('\n'.join(text))
    print(json.dumps(report,ensure_ascii=False))
    return report
if __name__=='__main__':run()
