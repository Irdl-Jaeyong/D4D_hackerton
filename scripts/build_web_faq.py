#!/usr/bin/env python3
"""Korean question adaptations, with separately attributed source facts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Source summaries are brief paraphrases. Questions/application options are ours.
GROUPS=[
('battery','배터리', 'https://ardupilot.org/copter/docs/failsafe-battery.html','ArduPilot Battery Failsafe',
 '저전압과 잔여 용량에 따른 보호 동작을 구성할 수 있으며 배터리 계측이 필요합니다.',
 '배터리 수치·계측 장치·복귀 여유와 해당 기체의 설정을 확인',
 ['배터리 몇 퍼센트면 드론을 복귀시켜야 해?','배터리 잔량만 높으면 멀리 보내도 돼?','저전압 경고와 잔량 부족은 같은 거야?','배터리 경고가 뜨면 무조건 바로 착륙해?','배터리가 두 개면 하나의 잔량만 보면 돼?','배터리 숫자가 이상하면 뭘 확인해야 해?']),
('rc','조종 링크','https://ardupilot.org/copter/docs/radio-failsafe.html','ArduPilot Radio Failsafe',
 '조종 링크 상실 대응은 설정에 따라 다릅니다. 링크가 복구되어도 이전 비행 모드로 자동 복원되지 않을 수 있습니다.',
 '문제 기체·마지막 수신 시각·현재 모드·조종 링크의 실제 상태를 확인',
 ['조종기 연결이 끊기면 드론은 어떻게 돼?','조종기 전원을 꺼도 임무가 계속돼?','신호가 돌아오면 이전 임무로 바로 돌아가?','통신이 잠깐 끊겼다가 붙으면 정상으로 봐도 돼?','조종 링크 고장인지 드론 고장인지 어떻게 구분해?','조종기 신호가 끊기는 상황을 어떻게 검증해?']),
('gcs','관제 링크','https://docs.px4.io/main/en/config/safety','PX4 Safety Configuration',
 '관제 데이터 링크와 외부 제어 링크의 상실 조건 및 대응 설정은 구분됩니다.',
 '관제 링크인지 외부 제어 링크인지·현재 모드·수신 시각·설정된 대응을 확인',
 ['관제 화면 연결이 끊기면 드론도 조종 불가야?','데이터 링크와 조종기 링크는 다른 거야?','오프보드 명령이 끊기면 어떻게 확인해?','통신 타임아웃은 몇 초로 정해야 해?','영상이 멈추면 모든 통신이 끊겼다는 뜻이야?','관제 서버가 꺼지면 어떤 동작을 하도록 준비해야 해?']),
('position','위치 신뢰도','https://docs.px4.io/main/en/config/safety','PX4 Safety Configuration',
 '위치 추정이 무효해지면 위치를 요구하는 비행 모드의 보호 동작이 적용될 수 있습니다.',
 '위치 추정 신뢰도·현재 모드·최근 센서 수신과 함선 위치를 확인',
 ['GPS가 안 잡히면 무조건 복귀할 수 있어?','위치가 지도에서 튀면 그 좌표로 보내도 돼?','GPS가 없어도 대형 유지가 가능해?','위치 오차가 크면 어느 기체를 제외해야 해?','고도는 있는데 수평 위치가 없으면 정상 비행이야?','GPS 두 개가 서로 다른 위치를 말하면 어떻게 봐야 해?']),
('fence','운용 경계','https://docs.px4.io/main/en/config/safety','PX4 Safety Configuration',
 '지오펜스는 설정된 운용 경계를 넘었을 때의 대응을 구성하는 기능입니다.',
 '허용 구역·위치 신뢰도·경계 설정과 전환 경로를 확인',
 ['드론이 지정 구역 밖으로 나가면 어떻게 해?','드론 최대 운용 거리는 몇 미터로 해야 해?','대형을 바꾸다가 운용 구역 밖으로 나가면?','고도 제한과 수평 거리 제한은 따로 봐야 해?','함선이 움직이는데 운용 경계는 어떻게 확인해?','경계 안에 있으면 경로가 안전하다는 뜻이야?']),
('prearm','출동 전 점검','https://ardupilot.org/copter/docs/common-prearm-safety-checks.html','ArduPilot Pre-Arm Safety Checks',
 '출동 전 검사에서 센서·교정·설정 등의 문제가 발견되면 시동이 제한될 수 있습니다.',
 '시동 거부 메시지·센서 교정·배터리·설정 오류와 정비 상태를 확인',
 ['드론이 아예 시동이 안 걸리면 뭘 봐?','출동 전 점검 오류를 무시해도 돼?','센서 교정을 안 했는데 잠깐만 띄워도 돼?','수행 불가인 드론이 떠 있으면 정상 화면이야?','정비 완료했다고 바로 임무에 넣으면 돼?','시동 거부 원인을 인터페이스에 어떻게 보여줘?']),
('logs','이상 원인 확인','https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html','ArduPilot Diagnosing Problems Using Logs',
 '로그의 목표 자세와 실제 자세 등을 비교하여 기계적 이상이나 보호 동작 여부를 조사할 수 있습니다.',
 '발생 시각·목표 자세·실제 자세·관련 이벤트 로그를 확인',
 ['드론이 흔들리면 프로펠러 고장이라고 보면 돼?','목표 자세와 실제 자세 차이는 왜 봐?','명령이 안 먹는 이유를 어떻게 조사해?','기계 고장과 소프트웨어 문제를 어떻게 비교해?','이상 발생 때 어떤 로그를 남겨야 해?','영상만 보고 고장 원인을 확정할 수 있어?']),
('simulation','시뮬레이션 검증','https://docs.px4.io/main/en/simulation/failsafes','PX4 Simulate Failsafes',
 'SITL에서는 일부 보호 동작과 배터리 모델이 실제 운용과 다르게 설정될 수 있으므로 고장 조건을 따로 시험해야 합니다.',
 '시뮬레이션 설정·고장 주입 조건·기대 동작·관측된 결과를 확인',
 ['시뮬레이션에서 성공하면 실제 배에서도 똑같이 돼?','시뮬 배터리가 안 줄어드는 건 왜 그래?','GPS 고장 상황도 시뮬레이션에서 시험할 수 있어?','통신 고장을 시험할 때 어떤 결과를 기록해?','고장 주입을 해제하면 바로 정상 임무로 돌려도 돼?','SITL과 실제 기체 검증은 같은 거야?']),
('marine','해상 항법 확인','https://www.navcen.uscg.gov/navigation-rules-faqs','USCG Navigation Rules FAQ',
 '이 FAQ는 선박의 항법 규칙과 관련 공식 자료를 다룹니다. 미국 자료의 관할 범위를 구분해야 합니다.',
 '운용 해역·상대 위치·진로·속도·현지 적용 규칙과 함장 판단을 확인',
 ['작은 무인배도 항법 규칙을 확인해야 해?','미국 항법 FAQ를 한국 바다에 그대로 써도 돼?','충돌 위험이 있으면 몇 미터에서 움직여야 해?','USV가 호위 대형을 유지하면 충돌 위험이 없어?','상대 선박이 양보할 거라고 가정해도 돼?','항법 규칙의 최신 공식 자료는 어디서 확인해?']),
('regulation','실제 운용 준비','https://www.faa.gov/uas/resources/faqs','FAA Drone FAQ',
 'FAA FAQ는 공역·허가·등록·조종 자격·사고 보고 등의 질문을 분류하여 제공합니다. 미국 기관 자료입니다.',
 '운용 국가·공역·임무 종류와 관할 기관의 최신 안내를 확인',
 ['바다 위면 드론 비행 허가가 필요 없어?','해상 드론을 띄우기 전에 어떤 허가를 확인해?','여러 드론을 동시에 운용하면 뭘 확인해야 해?','미국 드론 FAQ를 한국 프로젝트에 어떻게 참고해?','드론 사고가 나면 보고 기준은 어디서 확인해?','시뮬레이터가 있다는 이유로 실제 운용 준비가 끝난 거야?'])]
def build():
    topics=[];faqs=[]
    for topic,category,url,title,fact,check,questions in GROUPS:
        topics.append({'id':topic,'category':category,'source':{'title':title,'url':url,'checked_on':'2026-10-10'},'source_fact':fact,'application_check':check})
        for question in questions:
            n=len(faqs)+1
            faqs.append({'id':f'FAQ-{n:03d}','topic_id':topic,'question':question,'question_provenance':'공식 문서 주제를 프로젝트용 한국어 질문으로 재작성; 검색 빈도 측정 아님',
              'clarifying_question':check+'해주세요. 이미 확인된 값과 아직 모르는 부분을 구분해주세요.',
              'answers':[{'id':'observe','title':'현재 자료 확인','action':check+'합니다. 확인된 사실과 추정을 분리하고 기존 담당 구역을 유지합니다.','tradeoff':'정보 확인 전에는 새 임무의 가능 여부를 확정할 수 없습니다.'},
               {'id':'verify','title':'설정·근거 교차 확인','action':'해당 기체 또는 운용 환경의 설정·로그·공식 안내를 비교하고 확인 결과를 운용자에게 제시합니다.','tradeoff':'검토에는 시간이 필요하며 문서의 기능이 현재 시뮬레이터에 구현되어 있다는 뜻은 아닙니다.'},
               {'id':'prepare','title':'신규 출동 보류·검증 계획','action':'미확인 조건에 의존한 새 출동을 보류하는 안을 제시하고 시뮬레이션 시험 또는 담당자 검토 항목을 정리합니다.','tradeoff':'즉시 임무 확대보다 불확실성 해소를 우선합니다.'}],
               'automatic_execution':False,'scope':'웹 근거는 주제 사실만 지원. 세 가지 앱 대응안은 프로젝트 제안이며 원문의 공식 절차나 법률 판단이 아님.'})
    return {'version':1,'checked_on':'2026-10-10','count':len(faqs),'answer_count':len(faqs)*3,'topics':topics,'faqs':faqs}
if __name__=='__main__':
    data=build();(ROOT/'config/web_faq_60.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    lines=['공식 FAQ·운용 문서 기반 질문 60개 / 프로젝트 답변 180개','실제 질문 빈도 순위 아님. 질문은 한국어 재작성, 답변은 앱 검토 제안.','']
    for topic in data['topics']:lines.extend([topic['category'],topic['source']['title']+' '+topic['source']['url'],topic['source_fact'],''])
    for row in data['faqs']:
        lines.extend([row['id']+' '+row['question'],'추가 질문: '+row['clarifying_question']])
        for i,answer in enumerate(row['answers'],1):lines.append(f'{i}. {answer["title"]}: {answer["action"]} 한계: {answer["tradeoff"]}')
        lines.extend(['기체 추가 배정·명령 실행 없음.',''])
    (ROOT/'outputs/web_faq_60.txt').write_text('\n'.join(lines));print('60 questions, 180 application answers, 8 official sources')
