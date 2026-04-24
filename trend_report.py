"""
오늘의집 트렌드 레이더 - 리포트 생성 스크립트
GitHub Actions에서 실행되며, 리포트를 reports/ 폴더에 JSON으로 저장합니다.
"""

import anthropic
import json
import os
from datetime import datetime, timezone

REPORTS_DIR = "reports"

PROMPT = """당신은 오늘의집(Ohouse) 내부 트렌드 레이더 리포트를 작성하는 에디터입니다.
오늘 날짜: {date}

아래 수집 기준과 테마 분류에 따라 트렌드 리포트를 JSON 형식으로 생성해주세요.

[수집 기준]
- 포함: 뉴스 기사, 고구마팜(gogumafarm.kr), 오픈애즈(openads.co.kr), 무신사 뉴스룸(newsroom.musinsa.com), 29CM(29cm.co.kr), 지그재그 등 공식 채널
- 포함: 노트폴리오 인스타그램, 아이즈매거진 인스타그램 최근 게시물
- 제외: 네이버 블로그, 티스토리, 브런치, 개인 블로그
- 기간: 오늘 기준 최근 2주 이내
- 제외 조건: '#광고' 포함, 단순 아이돌/음악/연예 소식
- 키워드 포함 필수: 인테리어, 커머스, 29CM, 무신사, 지그재그, 라이프스타일, 트렌드, 유행, 스토어, 콜라보, 가구, 마케팅 중 하나 이상

[테마 분류]
- interior: 인테리어 관련 소식, 전시, 동향
- marketing: 브랜드 캠페인, 마케팅 동향, 트렌드/유행
- lifestyle: 계절 아이템, 주거/생활 소비 트렌드
- commerce: 커머스 트렌드, 백화점 동향, 커머스 기술

[소스 균형]
테마별로 뉴스, 전문 미디어, SNS 골고루. 한 소스에서 같은 테마 3개 이상 금지.

중요: 반드시 아래 JSON만 반환하세요. 코드블록(```)이나 설명 텍스트 없이 순수 JSON만.
{{
  "title": "{mon}월 {day}일 트렌드 레이더",
  "items": [
    {{
      "theme": "interior",
      "title": "기사 제목",
      "url": "https://실제존재하는URL",
      "source": "매체명",
      "summary": "1~2줄 요약"
    }}
  ]
}}

각 테마별 2~4건, 총 8~14건. 실제로 접근 가능한 URL만 포함하세요.
절대로 JSON 앞뒤에 다른 텍스트를 붙이지 마세요."""


def generate_report() -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    mon = now.month
    day = now.day

    prompt = PROMPT.format(date=date_str, mon=mon, day=day)

    print(f"[{date_str}] 트렌드 리포트 생성 시작...")

    # web_search 없이 단순 호출 → 응답이 항상 text 블록 하나로 옴
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    # 텍스트 블록 추출
    text_blocks = [b.text for b in response.content if b.type == "text"]
    if not text_blocks:
        raise ValueError("API 응답에 텍스트 블록이 없습니다.")

    text = "\n".join(text_blocks).strip()
    print(f"  → 응답 길이: {len(text)}자")

    # JSON 정리 (혹시 모를 코드블록 제거)
    clean = text
    if "```" in clean:
        parts = clean.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                clean = stripped
                break

    clean = clean.strip()

    if not clean:
        raise ValueError(f"파싱할 텍스트가 비어있습니다. 원본 응답:\n{text[:500]}")

    parsed = json.loads(clean)
    item_count = len(parsed.get("items", []))
    print(f"  → {item_count}건 수집 완료")
    return parsed


def save_report(parsed: dict) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    report_id = "w" + date_str.replace("-", "")

    report = {
        "id": report_id,
        "date": date_str,
        "title": parsed.get("title", f"{now.month}월 {now.day}일 트렌드 레이더"),
        "items": parsed.get("items", []),
    }

    # 개별 리포트 저장
    report_path = os.path.join(REPORTS_DIR, f"{report_id}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  → 저장: {report_path}")

    # index.json 갱신
    index_path = os.path.join(REPORTS_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    index = [item for item in index if item["id"] != report_id]
    index.insert(0, {
        "id": report_id,
        "date": date_str,
        "title": report["title"],
        "count": len(report["items"]),
    })

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"  → index.json 갱신 ({len(index)}개 리포트)")

    return report_id


if __name__ == "__main__":
    try:
        parsed = generate_report()
        report_id = save_report(parsed)
        print(f"\n✅ 완료: {report_id}")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        raise
