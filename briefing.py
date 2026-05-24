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
    ("투자", "보유