import os
import requests
import pytz
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID")
SHEETS_ID      = os.environ.get("SHEETS_ID", "")

KST = pytz.timezone("Asia/Seoul")

def get_today_str():
    now  = datetime.now(KST)
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return f"{now.strftime('%Y.%m.%d')} {days[now.weekday()]}요일"

def get_tickers_from_sheets():
    default = {
        "이현규": ["VRT", "OII", "BWXT", "TEM", "ALAB"],
        "임인숙": ["MSFT", "GOOGL", "NVDA", "UNH", "QQQ"],
    }
    if not SHEETS_ID:
        return default
    try:
        url = (
            f"https://docs.google.com/spreadsheets/d/{SHEETS_ID}"
            "/gviz/tq?tqx=out:csv&sheet=tickers"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        tickers = {}
        for line in lines[1:]:
            parts = line.replace('"', '').split(",")
            if len(parts) >= 2:
                owner  = parts[0].strip()
                ticker = parts[1].strip()
                if owner not in tickers:
                    tickers[owner] = []
                if ticker not in tickers[owner]:
                    tickers[owner].append(ticker)
        return tickers if tickers else default
    except Exception:
        return default

def get_stock_data(tickers):
    try:
        import yfinance as yf
    except ImportError:
        return ["yfinance 미설치"]
    results = []
    for ticker in tickers:
        try:
            t    = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev  = hist["Close"].iloc[-2]
                today = hist["Close"].iloc[-1]
                pct   = (today - prev) / prev * 100
                sign  = "▲" if pct > 0 else "▼" if pct < 0 else "─"
                results.append(f"{ticker}: {sign}{abs(pct):.1f}% (${today:.2f})")
            else:
                results.append(f"{ticker}: 데이터 없음")
        except Exception:
            results.append(f"{ticker}: 조회 실패")
    return results

def generate_ai_comment(stock_summary):
    if not GEMINI_API_KEY:
        return "오늘도 원칙대로. 단기 변동보다 보유 이유가 변했는지 먼저 확인."
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = f"""
너는 이현규(뀨)의 개인 투자 비서다.
오늘 포트폴리오 현황을 보고 딱 3줄로 코멘트를 써라.

[현황]
{stock_summary}

[작성 규칙]
- 3줄 이내
- 감성적 표현 금지
- 구체적이고 실용적으로
- 마지막 줄: 오늘 지킬 투자 원칙 1개
"""
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return "오늘도 원칙대로. 단기 변동보다 보유 이유가 변했는지 먼저 확인."

MISSIONS = [
    ("학교", "세특 문체 해독기에 '학생은' 표현 감지 기능 추가", "샘플 문장 3개에서 감지되면 성공"),
    ("투자", "보유 종목을 장기확신/관망/재검토로 분류해보기", "5종목 분류 완료"),
    ("가족", "이재연 항공사 면접 질문 5개 생성하기", "질문 5개 완성"),
    ("창작", "인상주의 화풍 이미지 프롬프트 3개 만들기", "프롬프트 3개 완성"),
    ("학교", "진로 상담 메모를 후속 질문 3개로 변환", "상담 예시 1건 처리"),
    ("투자", "투자 원칙 카드 5개 텍스트로 정리", "원칙 5개 작성 완료"),
    ("시스템", "브리핑 봇 메시지 길이 조정 실험", "30초 내 읽기 가능"),
]

def get_todays_mission():
    now = datetime.now(KST)
    day_of_year = now.timetuple().tm_yday
    return MISSIONS[day_of_year % len(MISSIONS)]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message)
        return 0
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code
    except Exception as e:
        print(f"텔레그램 발송 실패: {e}")
        return -1

def main():
    today   = get_today_str()
    TICKERS = get_tickers_from_sheets()

    account_blocks = []
    all_lines      = []
    for owner, tickers in TICKERS.items():
        lines = get_stock_data(tickers)
        account_blocks.append(f"💹 {owner} 계좌\n" + "\n".join(lines))
        all_lines.extend(lines)

    stock_summary = "\n".join(all_lines)
    ai_comment    = generate_ai_comment(stock_summary)
    cat, mission_title, success_cond = get_todays_mission()

    message = f"""🛰 뀨의 AI 임무 통제실
{today}

{chr(10).join(account_blocks)}

🤖 AI 코멘트
{ai_comment}

🧪 오늘의 빌드 미션 [{cat}]
{mission_title}
✅ 성공 기준: {success_cond}

오늘 하나만 끝내자."""

    status = send_telegram(message)
    print(f"발송 상태: HTTP {status}")
    print(message)

if __name__ == "__main__":
    main()