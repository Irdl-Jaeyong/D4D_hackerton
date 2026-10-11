'use strict';
globalThis.RecordUIState = Object.freeze({
  visible(records, mode, query='') {
    const term=query.trim().toLowerCase();
    return records.filter(r => (mode === 'all' || (mode === 'read' ? r.read : !r.read)) &&
      (!term || [r.id,r.device,r.status,r.raw].some(v=>String(v??'').toLowerCase().includes(term))));
  },
  selected(records, mode, id, query='') {
    const visible = this.visible(records, mode, query);
    return visible.some(r => r.id === id) ? id : visible[0]?.id ?? null;
  },
  markRead(records, id) {
    return records.map(r => r.id === id ? {...r, read: true} : r);
  },
  snapshot(record, question) {
    if (!record || !question.trim()) throw Error('기록과 질문이 필요합니다.');
    return Object.freeze({id: record.id, time: record.time, question: question.trim()});
  },
  validEvidence(result, snapshot) {
    return typeof result?.answer === 'string' && typeof result?.answerable === 'boolean' &&
      result?.evidence?.record_id === snapshot.id && result?.evidence?.record_time === snapshot.time &&
      Array.isArray(result?.supporting_quotes) && result.supporting_quotes.every(q => typeof q === 'string');
  },
  createMeasurement() {
    return {active: null, trials: [],
      start(mode, now) {if(this.active) throw Error('이미 측정 중입니다.'); this.active={mode,start:now,clicks:0,questions:0};},
      click() {if(this.active) this.active.clicks++;},
      question() {if(this.active) this.active.questions++;},
      stop(now) {if(!this.active) throw Error('측정이 시작되지 않았습니다.');
        const a=this.active, row={trial:this.trials.length+1,mode:a.mode,elapsed_ms:Math.max(0,Math.round(now-a.start)),click_count:a.clicks,question_count:a.questions};
        this.trials.push(row);this.active=null;return row;},
      csv() {return 'trial,condition,elapsed_ms,ui_click_events,question_requests\r\n'+this.trials.map(t=>[t.trial,t.mode,t.elapsed_ms,t.click_count,t.question_count].join(',')).join('\r\n');}
    };
  }
});
