"""Supervised character n-gram centroid classifier, independent from Qwen weights."""
import json,re,math
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/'config/training/intent_model.json'
def features(text):
 text=re.sub(r'(?:UAV|USV|SHIP)-\d{2}','',text,flags=re.I);text=re.sub(r'[^가-힣a-z]','',text.lower())
 return Counter(text[i:i+n] for n in (1,2,3) for i in range(max(0,len(text)-n+1)))
def unit(v):
 norm=math.sqrt(sum(x*x for x in v.values()));return {k:x/norm for k,x in v.items()} if norm else {}
def train():
 rows=[json.loads(l) for l in (PATH.parent/'intent_train.jsonl').read_text().splitlines()];df=Counter();groups=defaultdict(Counter)
 for r in rows:df.update(features(r['text']).keys())
 idf={k:math.log((len(rows)+1)/(n+1))+1 for k,n in df.items()}
 for r in rows:groups[r['intent']].update(unit({k:n*idf[k] for k,n in features(r['text']).items()}))
 model={'version':1,'type':'supervised_ngram_prototypes','training_examples':len(rows),'idf':idf,'centroids':{k:unit(v) for k,v in groups.items()},'prototypes':[{'intent':r['intent'],'vector':unit({k:n*idf[k] for k,n in features(r['text']).items()})} for r in rows]}
 PATH.write_text(json.dumps(model,ensure_ascii=False));return model
def predict(text):
 model=json.loads(PATH.read_text());v=unit({k:n*model['idf'][k] for k,n in features(text).items() if k in model['idf']})
 scores=sorted(((max(sum(x*p['vector'].get(k,0) for k,x in v.items()) for p in model['prototypes'] if p['intent']==intent),intent) for intent in model['centroids']),reverse=True)
 score,label=scores[0];margin=score-scores[1][0]
 return {'intent':label if score>=.25 and margin>=.035 else 'unknown','score':round(score,3),'margin':round(margin,3),'classifier':'trained_ngram_prototypes'}
if __name__=='__main__':
 model=train();rows=[json.loads(l) for l in (PATH.parent/'intent_test.jsonl').read_text().splitlines()];correct=0;errors=[]
 for r in rows:
  got=predict(r['text']);correct+=got['intent']==r['intent']
  if got['intent']!=r['intent']:errors.append({'text':r['text'],'expected':r['intent'],'prediction':got})
 report={'training_examples':model['training_examples'],'test_examples':len(rows),'correct':correct,'accuracy':correct/len(rows),'errors':errors,'limitations':'소규모 합성 문장 평가. 실제 운용 정확도나 LLM 가중치 학습을 의미하지 않음.'};(PATH.parent/'intent_evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
