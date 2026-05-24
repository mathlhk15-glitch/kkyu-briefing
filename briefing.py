import os
import requests
import pytz
import random
from datetime import datetime, date

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
SHEETS_ID      = os.environ.get("SHEETS_ID", "1gCqG1t0HIwTYvt-CQFZz-5K96hW5krhDWrUWq-KBlUI")
CALENDAR_ICS   = os.environ.get("CALENDAR_ICS", "https://calendar.google.com/calendar/ical/lhk15%40cwgyeongilg-h.gne.go.kr/private-5a0f7c194581f0930c87b167e8716cb4/basic.ics")
RUN_TYPE       = os.environ.get("RUN_TYPE", "daily")

CHAT_IDS       = ["8980336176", "8827812313"]
DISCHARGE_DATE = date(2027, 7, 26)
CHANGWON_LAT   = 35.2279
CHANGWON_LON   = 128.6811

KST = pytz.timezone("Asia/Seoul")

def get_today_str():
    now  = datetime.now(KST)
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return f"{now.strftime('%Y.%m.%d')} {days[now.weekday()]}요일"

def get_weather():
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={CHANGWON_LAT}&longitude={CHANGWON_LON}"
            "&current=temperature_2m,precipitation_probability,weathercode"
            "&timezone=Asia%2FSeoul"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data    = resp.json()
        current = data["current"]
        temp    = current["temperature_2m"]
        precip  = current["precipitation_probability"]
        code    = current["weathercode"]
        weather_map = {
            0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
            45: "안개", 48: "안개",
            51: "이슬비", 53: "이슬비", 55: "이슬비",
            61: "비", 63: "비", 65: "강한 비",
            71: "눈", 73: "눈", 75: "강한 눈",
            80: "소나기", 81: "소나기", 82: "강한 소나기",
            95: "뇌우", 96: "뇌우", 99: "뇌우"
        }
        weather_desc = weather_map.get(code, "알 수 없음")
        return f"{weather_desc} {temp}C / 강수확률 {precip}%"
    except Exception:
        return "날씨 조회 실패"

def get_discharge_dday():
    today = datetime.now(KST).date()
    dday  = (DISCHARGE_DATE - today).days
    if dday < 0:
        return "이재현 전역 완료"
    elif dday == 0:
        return "이재현 오늘 전역!"
    elif dday <= 7:
        return f"이재현 전역 D-{dday} 거의 다 왔다!"
    elif dday <= 30:
        return f"이재현 전역 D-{dday} 한 달 남음"
    else:
        return f"이재현 전역 D-{dday}"

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

def get_mission_from_sheets():
    default = ["학교", "진로 상담 메모를 후속 질문으로 변환", "상담 예시 1건 처리"]
    if not SHEETS_ID:
        return default
    try:
        url = (
            "https://docs.google.com/spreadsheets/d/" + SHEETS_ID
            + "/gviz/tq?tqx=out:csv&sheet=mission_pool"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        missions = []
        for line in lines[1:]:
            parts = line.replace('"', '').split(",")
            if len(parts) >= 4:
                missions.append([
                    parts[0].strip(),
                    parts[2].strip(),
                    parts[3].strip(),
                ])
        if missions:
            return random.choice(missions)
        return default
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

def get_weekly_stock_data(tickers):
    try:
        import yfinance as yf
    except ImportError:
        return ["yfinance 미설치"]
    results = []
    for ticker in tickers:
        try:
            t    = yf.Ticker(ticker)
            hist = t.history(period="7d")
            if len(hist) >= 2:
                start = hist["Close"].iloc[0]
                end   = hist["Close"].iloc[-1]
                pct   = (end - start) / start * 100
                arrow = "▲" if pct > 0 else "▼" if pct < 0 else "─"
                results.append(ticker + ": " + arrow + str(round(abs(pct),1)) + "% 주간")
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

def generate_weekly_ai_comment(stock_summary):
    if not GEMINI_API_KEY:
        return "이번 주 포트폴리오를 점검하고 다음 주 원칙을 세워라."
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
    )
    prompt = (
        "너는 이현규의 주간 투자 비서다.\n"
        "아래 이번 주 포트폴리오 수익률을 보고 다음 형식으로 작성해라.\n\n"
        "1. 이번 주 한 줄 평가\n"
        "2. 가장 주목할 종목 1개와 이유\n"
        "3. 다음 주 지킬 원칙 1개\n\n"
        + stock_summary
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return "이번 주 포트폴리오를 점검하고 다음 주 원칙을 세워라."

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

def run_weekly():
    today   = get_today_str()
    TICKERS = get_tickers_from_sheets()

    account_blocks = []
    all_lines      = []
    for owner, tickers in TICKERS.items():
        lines = get_weekly_stock_data(tickers)
        block = "💹 " + owner + " 계좌 (주간)\n" + "\n".join(lines)
        account_blocks.append(block)
        all_lines.extend(lines)

    stock_summary = "\n".join(all_lines)
    ai_comment    = generate_weekly_ai_comment(stock_summary)

    msg_lines = []
    msg_lines.append("📊 뀨의 주간 포트폴리오 리포트")
    msg_lines.append(today)
    msg_lines.append("")
    for block in account_blocks:
        msg_lines.append(block)
        msg_lines.append("")
    msg_lines.append("🤖 주간 AI 코멘트")
    msg_lines.append(ai_comment)
    msg_lines.append("")
    msg_lines.append("다음 주도 원칙대로.")
    message = "\n".join(msg_lines)

    status = send_telegram(message)
    print("주간 리포트 발송: HTTP " + str(status))
    print(message)

def run_daily():
    today           = get_today_str()
    weather         = get_weather()
    discharge       = get_discharge_dday()
    calendar_events = get_todays_events()
    TICKERS         = get_tickers_from_sheets()
    mission         = get_mission_from_sheets()
    cat             = mission[0]
    mission_title   = mission[1]
    success_cond    = mission[2]

    account_blocks = []
    all_lines      = []
    for owner, tickers in TICKERS.items():
        lines = get_stock_data(tickers)
        block = "💹 " + owner + " 계좌\n" + "\n".join(lines)
        account_blocks.append(block)
        all_lines.extend(lines)

    stock_summary = "\n".join(all_lines)
    ai_comment    = generate_ai_comment(stock_summary)

    msg_lines = []
    msg_lines.append("🛰 뀨의 AI 임무 통제실")
    msg_lines.append(today)
    msg_lines.append("")
    msg_lines.append("🌤 창원 날씨: " + weather)
    msg_lines.append("🪖 " + discharge)
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
    print("일간 브리핑 발송: HTTP " + str(status))
    print(message)

def main():
    if RUN_TYPE == "weekly":
        run_weekly()
    else:
        run_daily()

if __name__ == "__main__":
    main()