"""Immutable, prerecorded text changes. No simulator or device integration."""
from types import MappingProxyType

TEXTS = (
    ("예시 문장을 불러왔습니다.", "예시 문장이 아직 제공되지 않았습니다.", "예시 문자열을 기록했습니다."),
    ("두 번째 예시 문장을 기록했습니다.", "새 예시 문장을 기록했습니다.", "이 단계에서는 새 예시 문장이 없습니다."),
    ("예시 기록 재생이 끝났습니다.", "마지막 예시 문장을 기록했습니다.", "예시 기록 재생이 끝났습니다."),
)
FRAMES = tuple(tuple(MappingProxyType({
    "id": f"PLAY-{letter}-{frame + 1:03d}", "device": f"장치 {letter}",
    "time": f"2026-10-10T10:00:{frame * 5:02d}+09:00",
    "status": text, "raw": text + " 합성 텍스트 재생이며 실제 장치의 상태·연결·해결 여부는 확인할 수 없습니다.",
}) for letter, text in zip("ABC", texts)) for frame, texts in enumerate(TEXTS))
