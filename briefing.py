import os
import requests
import pytz
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID")
SHEETS_ID      = os.environ.get("SHEETS_ID", "1gCqG1t0HIwTYvt-CQFZz-5K96hW5krhDWrUWq-KBlUI")
CALENDAR_ICS   = os.environ.get("CALENDAR_ICS", "")

CHAT_IDS = ["8980336176", "8827812313"]

KST = pytz.timezone("Asia/Seoul")

def get_today_str():
    now  = datetime.now(KST)
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return f"{now.strftime('%Y.%m.%d')} {days[now.weekday()]}요일"

def get_todays_events():
    if not CALENDAR_ICS:
        return "캘린더 미연동"
    try:
        from icalendar import Calendar
        resp = requests.get(CALENDAR_ICS, timeout=10)
        resp.raise_for_status()
        cal   = Calendar.from_ical(resp.content)
        today = datetime.now(KST).date()
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                dtstart = component.get("DTSTART")
                if dtstart:
                    dt = dtstart.dt
                    if hasattr(dt, "date"):
                        dt = dt.date()
                    if dt == today:
                        summary = str(component.get("SUMMARY", "제목없음"))
                        events.append(summary)
        if events:
            return "\n".join(f"• {e}" for e in events)
        return "오늘 일정 없음"
    except Exception:
        return "캘린더 읽기 실패"

def get_tickers_from_sheets():
    default = {
        "이현규": ["VRT", "OII", "BWXT", "TEM", "ALAB"],
        "임인숙": ["MSFT", "GOOGL", "NVDA", "UNH", "QQQ"],
    }
    if not SHEETS_ID:
        return default
    try:
        url = (
            "https://docs.google.com/spreadsheets/d/" + SHEETS_ID
            + "/gviz/tq?tqx=out:csv&sheet=tickers"
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
                arrow = "▲" if pct > 0 else "▼" if pct < 0 else "─"
                results.append(ticker + ": " + arrow + str(round(abs(pct),1)) + "% ($" + str(round(today,2)) + ")")
            else:
                results.append(ticker + ": 데이터 없음")
        except Exception:
            results.append(ticker + ": 조회 실패")
    return results

def generate_ai_comment(stock_summary):
    if not GEMINI_API_KEY:
        return "오늘도 원칙대로. 단기 변동보다 보유 이유가 변했는지 먼저 확인."
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
    )
    prompt = "너는 이현규의 투자 비서다. 아래 포트폴리오를 보고 3줄 이내로 코멘트해라. 마지막 줄은 오늘 지킬 원칙 1개.\n\n" + stock_summary
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return "오늘도 원칙대로. 단기 변동보다 보유 이유가 변했는지 먼저 확인."

MISSIONS = [
    ["학교", "세특 문체 해독기 개선", "샘플 3개 테스트 완료"],
    ["투자", "보유 종목 장기확신/관망/재검토 분류", "5종목 분류 완료"],
    ["가족", "이재연 면접 질문 5개 생성", "질문 5개 완성"],
    ["창작", "인상주의 이미지 프롬프트 3개 작성", "프롬프트 3개 완성"],
    ["학교", "진로 상담 메모를 후속 질문으로 변환", "상담 예시 1건 처리"],
    ["투자", "투자 원칙 카드 5개 정리", "원칙 5개 작성"],
    ["시스템", "브리핑 메시지 길이 조정", "30초 내 읽기 가능"],
]

def get_todays_mission():
    now = datetime.now(KST)
    idx = now.timetuple().tm_yday % len(MISSIONS)
    return MISSIONS[idx]

def send_telegram(message):
    if not TELEGRAM_TOKEN:
        print(message)
        return 0
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
        except Exception as e:
            print("발송 실패 (" + chat_id + "): " + str(e))
    return 200

def main():
    today           = get_today_str()
    calendar_events = get_todays_events()
    TICKERS         = get_tickers_from_sheets()

    account_blocks = []
    all_lines      = []
    for owner, tickers in TICKERS.items():
        lines = get_stock_data(tickers)
        block = "💹 " + owner + " 계좌\n" + "\n".join(lines)
        account_blocks.append(block)
        all_lines.extend(lines)

    stock_summary = "\n".join(all_lines)
    ai_comment    = generate_ai_comment(stock_summary)
    mission       = get_todays_mission()
    cat           = mission[0]
    mission_title = mission[1]
    success_cond  = mission[2]

    msg_lines = []
    msg_lines.append("🛰 뀨의 AI 임무 통제실")
    msg_lines.append(today)
    msg_lines.append("")
    msg_lines.append("📅 오늘의 일정")
    msg_lines.append(calendar_events)
    msg_lines.append("")
    for block in account_blocks:
        msg_lines.append(block)
        msg_lines.append("")
    msg_lines.append("🤖 AI 코멘트")
    msg_lines.append(ai_comment)
    msg_lines.append("")
    msg_lines.append("🧪 오늘의 빌드 미션 [" + cat + "]")
    msg_lines.append(mission_title)
    msg_lines.append("성공 기준: " + success_cond)
    msg_lines.append("")
    msg_lines.append("오늘 하나만 끝내자.")
    message = "\n".join(msg_lines)

    status = send_telegram(message)
    print("발송 상태: HTTP " + str(status))
    print(message)

if __name__ == "__main__":
    main()