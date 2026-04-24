"""
오늘의집 트렌드 레이더 - 리포트 생성 스크립트
GitHub Actions에서 실행되며, 리포트를 reports/ 폴더에 JSON으로 저장합니다.
"""

import anthropic
import json
import os
from datetime import datetime, timezone

# ── 설정 ──────────────────────────────────────────────────────────────────────
REPORTS_DIR = "reports"
RSS_FEEDS = [
    "https://rss.app/feeds/fiWMc373dUUlqD2F.xml",  # 노트폴리오 인스타그램
    "https://rss.app/feeds/K7ZRC5b0y0rJZ6j6.xml",  # 아이즈매거진 인스타그램
]

PROMPT = """당신은 오늘의집(Ohouse) 내부 트렌드 레이더 리포트를 작성하는 에디터입니다.
오늘 날짜: {date}

아래 조건으로 트렌드 리포트를 생성해주세요.

[수집 대상]
- 뉴스 기사 (언론사 공식 사이트)
- 마케팅/트렌드 전문 미디어: 고구마팜(gogumafarm.kr), 오픈애즈(openads.co.kr)
- 기업 공식 뉴스룸: newsroom.musinsa.com, 29cm.co.kr 등
- RSS 피드 (반드시 직접 읽어서 내용 확인):
  {rss_feeds}
- 웹서치 중 인스타그램 또는 트위터(X) 게시물이 검색 결과에 노출되는 경우 포함

[제외 소스]
- 네이버 블로그, 티스토리, 브런치, 개인 블로그, 쇼핑몰 블로그, 해외 매체 번역 콘텐츠

[필터링 조건]
1. 오늘 기준 최근 2주 이내 발행된 콘텐츠만
2. 본문 또는 제목에 '#광고' 텍스트가 있으면 제외
3. 아래 키워드 중 하나 이상 포함:
   인테리어, 커머스, 29CM, 무신사, 지그재그, 라이프스타일,
   트렌드, 유행, 스토어, 콜라보, 가구, 마케팅
4. 제외: 단순 아이돌/가수/배우 소식, 음악 앨범/콘서트/페스티벌, 연예 콘텐츠

[소스 균형]
- 테마별로 뉴스 기사, 전문 미디어, 인스타그램 RSS 골고루 섞기
- 한 소스에서 같은 테마 3개 이상이면 중요도 낮은 것 제외

[테마 분류]
- interior: 인테리어 관련 소식, 전시, 최근 동향
- marketing: 브랜드 캠페인, 마케팅 동향, 트렌드/유행
- lifestyle: 계절 아이템, 주거/생활 소비 트렌드
- commerce: 커머스 트렌드, 백화점 동향, 커머스 기술

반드시 아래 JSON 형식만 반환하세요 (코드블록이나 설명 없이 순수 JSON만):
{{
  "title": "{mon}월 {day}일 트렌드 레이더",
  "items": [
    {{
      "theme": "interior|marketing|lifestyle|commerce",
      "title": "기사/게시물 제목",
      "url": "https://실제URL",
      "source": "매체명 또는 계정명",
      "summary": "내용 요약 1~2줄"
    }}
  ]
}}

각 테마별 2~4건, 총 8~14건. 실제로 존재하는 URL만 포함하세요."""


def generate_report() -> dict:
    """Anthropic API + web_search로 트렌드 리포트 생성"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    mon = now.month
    day = now.day

    prompt = PROMPT.format(
        date=date_str,
        rss_feeds="\n  ".join(RSS_FEEDS),
        mon=mon,
        day=day,
    )

    print(f"[{date_str}] 트렌드 리포트 생성 시작...")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # 텍스트 블록만 추출
    text = "\n".join(
        block.text for block in response.content if block.type == "text"
    )

    # JSON 파싱
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip()

    parsed = json.loads(clean)
    print(f"  → {len(parsed['items'])}건 수집 완료")
    return parsed


def save_report(parsed: dict) -> str:
    """리포트를 reports/ 폴더에 JSON으로 저장하고 index.json 갱신"""
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

    # index.json 갱신 (사이드바 목록용)
    index_path = os.path.join(REPORTS_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    # 같은 날짜 리포트가 있으면 교체
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
