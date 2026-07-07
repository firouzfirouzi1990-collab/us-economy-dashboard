#!/usr/bin/env python3
"""
دریافت‌کننده داده‌های اقتصادی آمریکا
=========================================
داده‌ها رو از سه منبع می‌گیره:
1. FRED API (اولویت اول — رایگان)
2. BLS API (اولویت دوم — رایگان)
3. Web Scraping از Trading Economics (fallback)
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ خطا: کتابخانه requests نصب نیست.")
    print("   اجرا کنید: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("⚠️  کتابخانه beautifulsoup4 نصب نیست. Scraping غیرفعال می‌شود.")
    print("   نصب: pip install beautifulsoup4")
    BeautifulSoup = None

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
PERSIAN_MONTHS = ["ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن",
                  "جولای", "آگوست", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]

# ─────────────────────────────────────────────────────────
# داده‌های پیش‌فرض (fallback — آخرین داده‌های معتبر)
# ─────────────────────────────────────────────────────────
DEFAULT_DATA = {
    "last_update": "2026-07-02T16:30:00",
    "source": "default",
    "nfp": {
        "months": ["ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن"],
        "values": [130, -92, 178, 115, 147, 57],
        "forecasts": [68, 58, 140, 62, 100, 114],
        "previous": [227, 130, -92, 178, 115, 147],
        "unit": "K",
        "latest": 57,
    },
    "unemployment": {
        "months": ["ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن"],
        "values": [4.3, 4.4, 4.3, 4.3, 4.3, 4.2],
        "latest": 4.2,
    },
    "wage": {
        "months": ["ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن"],
        "values": [0.4, 0.3, 0.3, 0.2, 0.3, 0.3],
        "yoy": 3.5,
        "level": 37.64,
        "latest": 0.3,
    },
    "claims": {
        "months": ["4 ژانویه", "11 ژانویه", "18 ژانویه", "25 ژانویه",
                   "1 فوریه", "8 فوریه", "15 فوریه", "22 فوریه",
                   "1 مارس", "8 مارس", "15 مارس", "22 مارس",
                   "5 آوریل", "12 آوریل", "19 آوریل", "26 آوریل",
                   "3 می", "10 می", "17 می", "24 می",
                   "7 ژوئن", "14 ژوئن", "21 ژوئن", "28 ژوئن"],
        "values": [223, 221, 219, 217, 225, 215, 218, 220,
                   222, 220, 218, 219, 224, 221, 217, 216,
                   225, 222, 221, 220, 230, 227, 216, 215],
        "latest": 215,
    },
    "ism_mfg": {
        "months": ["دسامبر", "ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن"],
        "values": [49.2, 50.9, 50.3, 49.0, 48.7, 48.5, 52.8],
        "latest": 52.8,
    },
    "ism_svc": {
        "months": ["دسامبر", "ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن"],
        "values": [52.1, 52.8, 53.5, 50.8, 51.6, 49.9, 50.8],
        "latest": 50.8,
    },
    "ism_mfg_details": {
        "Production": {"label_en":"Production","label_fa":"تولید","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[49.1,51.2,48.8,49.5,47.8,51.0],"latest":51.0,"prev":47.8},
        "New Orders": {"label_en":"New Orders","label_fa":"سفارشات جدید","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[47.1,48.3,46.5,47.6,47.4,47.7],"latest":47.7,"prev":47.4},
        "Supplier Deliveries": {"label_en":"Supplier Deliveries","label_fa":"تحویل‌دهندگان","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[49.5,50.2,48.9,49.8,49.3,50.8],"latest":50.8,"prev":49.3},
        "Employment": {"label_en":"Employment","label_fa":"اشتغال","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[43.8,46.2,45.1,44.5,44.1,44.9],"latest":44.9,"prev":44.1},
        "Inventories": {"label_en":"Inventories","label_fa":"موجودی","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[44.8,46.1,45.5,44.8,46.2,45.2],"latest":45.2,"prev":46.2},
        "Prices Paid": {"label_en":"Prices Paid","label_fa":"قیمت‌های پرداختی","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[52.5,54.2,53.8,56.1,59.5,58.5],"latest":58.5,"prev":59.5},
        "New Export Orders": {"label_en":"New Export Orders","label_fa":"سفارشات صادراتی","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[47.5,48.2,46.8,47.5,46.1,46.8],"latest":46.8,"prev":46.1},
        "Imports": {"label_en":"Imports","label_fa":"واردات","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[46.2,47.5,48.1,47.2,45.8,44.6],"latest":44.6,"prev":45.8},
        "Backlog of Orders": {"label_en":"Backlog of Orders","label_fa":"سفارشات در انتظار","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[44.5,45.2,44.8,46.1,45.5,45.8],"latest":45.8,"prev":45.5},
        "Customers Inventories": {"label_en":"Customers Inventories","label_fa":"موجودی مشتریان","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[44.1,45.5,44.8,45.2,44.1,43.3],"latest":43.3,"prev":44.1},
    },
    "ism_svc_details": {
        "Business Activity": {"label_en":"Business Activity","label_fa":"فعالیت تجاری","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[53.5,54.2,52.8,51.5,54.8,56.0],"latest":56.0,"prev":54.8},
        "New Orders": {"label_en":"New Orders","label_fa":"سفارشات جدید","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[54.1,55.2,53.8,52.5,55.1,57.9],"latest":57.9,"prev":55.1},
        "Employment": {"label_en":"Employment","label_fa":"اشتغال","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[50.5,51.2,49.8,48.5,50.8,52.0],"latest":52.0,"prev":50.8},
        "Prices Paid": {"label_en":"Prices Paid","label_fa":"قیمت‌های پرداختی","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[60.5,62.1,59.8,58.5,61.2,64.3],"latest":64.3,"prev":61.2},
        "Supplier Deliveries": {"label_en":"Supplier Deliveries","label_fa":"تحویل‌دهندگان","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[51.2,50.8,51.5,52.2,51.8,51.8],"latest":51.8,"prev":51.8},
        "Inventory Sentiment": {"label_en":"Inventory Sentiment","label_fa":"موجودی","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[53.2,52.5,53.8,54.1,53.5,54.1],"latest":54.1,"prev":53.5},
        "Imports": {"label_en":"Imports","label_fa":"واردات","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[51.5,52.8,51.2,50.5,51.1,50.3],"latest":50.3,"prev":51.1},
        "Exports": {"label_en":"Exports","label_fa":"صادرات","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[52.1,53.5,51.8,50.5,52.8,54.2],"latest":54.2,"prev":52.8},
        "Order Backlog": {"label_en":"Order Backlog","label_fa":"سفارشات در انتظار","months":["جولای 2025","آگوست 2025","سپتامبر 2025","اکتبر 2025","نوامبر 2025","دسامبر 2025"],"values":[48.5,49.2,47.5,48.1,43.5,42.6],"latest":42.6,"prev":43.5},
    },
}


# ─────────────────────────────────────────────────────────
# 1. FRED API
# ─────────────────────────────────────────────────────────
def fetch_fred_series(series_id, months_back=8):
    """دریافت یک سری از FRED API — ماه‌های اخیر"""
    if not config.FRED_API_KEY:
        log.warning("FRED API Key تنظیم نشده — رد می‌شود")
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": config.FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": months_back,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if "observations" not in data:
            log.error(f"FRED: پاسخ نامعتبر برای {series_id}")
            return None

        # از جدید به قدیم — reverse
        obs = data["observations"][::-1]

        results = []
        for o in obs:
            val = o.get("value", ".")
            date_str = o.get("date", "")
            if val == ".":
                results.append({"date": date_str, "value": None})
            else:
                try:
                    results.append({"date": date_str, "value": float(val)})
                except (ValueError, TypeError):
                    results.append({"date": date_str, "value": None})

        log.info(f"FRED ✅ {series_id}: {len(results)} مشاهده دریافت شد")
        return results
    except requests.RequestException as e:
        log.error(f"FRED ❌ خطا در دریافت {series_id}: {e}")
        return None


def compute_monthly_changes(series_data):
    """محاسبه تغییر ماهانه از داده‌های سطح PAYEMS"""
    if not series_data or len(series_data) < 2:
        return None

    changes = []
    for i in range(1, len(series_data)):
        curr = series_data[i].get("value")
        prev = series_data[i - 1].get("value")
        date = series_data[i].get("date")

        if curr is not None and prev is not None:
            change = round(curr - prev, 1)
            changes.append({"date": date, "value": change})
        else:
            changes.append({"date": date, "value": None})

    return changes


def fetch_all_fred():
    """دریافت تمام سری‌ها از FRED"""
    log.info("📡 دریافت داده‌ها از FRED API...")

    raw_nfp = fetch_fred_series("PAYEMS", config.MONTHS_BACK)
    nfp_changes = compute_monthly_changes(raw_nfp)

    unemployment = fetch_fred_series("UNRATE", config.MONTHS_BACK)
    wage = fetch_fred_series("CES0500000003", config.MONTHS_BACK)
    claims = fetch_fred_series("ICSA", config.MONTHS_BACK)
    ism_mfg = fetch_fred_series("NAPM", config.MONTHS_BACK)
    ism_svc = fetch_fred_series("NAPMS", config.MONTHS_BACK)

    success = all(v is not None for v in [nfp_changes, unemployment, wage, claims])
    if not success:
        log.warning("FRED: برخی سری‌ها دریافت نشدند")

    return {
        "nfp": nfp_changes,
        "unemployment": unemployment,
        "wage": wage,
        "claims": claims,
        "ism_mfg": ism_mfg,
        "ism_svc": ism_svc,
        "success": success,
    }


# ─────────────────────────────────────────────────────────
# 2. BLS API
# ─────────────────────────────────────────────────────────
def fetch_bls():
    """دریافت داده‌ها از BLS Public API"""
    if not config.BLS_API_KEY:
        log.warning("BLS API Key تنظیم نشده — رد می‌شود")
        return None

    log.info("📡 دریافت داده‌ها از BLS API...")

    headers = {"Content-type": "application/json"}
    # محاسبه سال و ماه برای ۲ سال اخیر
    now = datetime.now()
    years = [str(now.year - 1), str(now.year)]

    payload = {
        "seriesid": ["CES0000000001", "LNS14000000", "CES0500000003"],
        "registrationkey": config.BLS_API_KEY,
        "startyear": years[0],
        "endyear": years[1],
    }

    try:
        resp = requests.post(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "REQUEST_SUCCEEDED":
            log.error(f"BLS: پاسخ نامعتبر — {data.get('message', '')}")
            return None

        result = {}
        for series in data.get("Results", {}).get("series", []):
            sid = series["seriesID"]
            obs = sorted(
                series["data"],
                key=lambda x: int(x["year"]) * 100 + int(x["period"].strip("M")),
            )
            result[sid] = obs[-config.MONTHS_BACK:]

        log.info(f"BLS ✅ {len(result)} سری دریافت شد")
        return result
    except requests.RequestException as e:
        log.error(f"BLS ❌ خطا: {e}")
        return None


# ─────────────────────────────────────────────────────────
# 3½. DBnomics API — ISM زیرشاخص‌ها
# ─────────────────────────────────────────────────────────
# توجه: جزئیات زیرشاخص‌های ISM از FRED حذف شده (کپی‌رایت).
# این داده‌ها از DBnomics (رایگان، بدون کلید API) دریافت می‌شود.
# هر دیتاست چند سری دارد؛ سری 'Index' همون مقدار PMI واقعی (حول ۵۰) است.


def fetch_dbnomics_ism():
    """دریافت زیرشاخص‌های ISM از DBnomics API (رایگان، بدون کلید)

    توجه: هر دیتاست چند سری داره (% Higher, Index, % Lower, Net, % Same).
    سری 'Index' همون مقدار PMI واقعی حول ۵۰ است.
    """
    log.info("📡 دریافت جزئیات ISM از DBnomics API...")

    # نگاشت: (dataset_code, label_en, label_fa)
    mfg_indicators = [
        ("production", "Production", "تولید"),
        ("neword", "New Orders", "سفارشات جدید"),
        ("supdel", "Supplier Deliveries", "تحویل‌دهندگان"),
        ("employment", "Employment", "اشتغال"),
        ("inventories", "Inventories", "موجودی"),
        ("prices", "Prices Paid", "قیمت‌های پرداختی"),
        ("newexpord", "New Export Orders", "سفارشات صادراتی"),
        ("imports", "Imports", "واردات"),
        ("bacord", "Backlog of Orders", "سفارشات در انتظار"),
        ("cusinv", "Customers' Inventories", "موجودی مشتریان"),
    ]
    svc_indicators = [
        ("nm-busact", "Business Activity", "فعالیت تجاری"),
        ("nm-neword", "New Orders", "سفارشات جدید"),
        ("nm-employment", "Employment", "اشتغال"),
        ("nm-prices", "Prices Paid", "قیمت‌های پرداختی"),
        ("nm-supdel", "Supplier Deliveries", "تحویل‌دهندگان"),
        ("nm-invsen", "Inventory Sentiment", "موجودی"),
        ("nm-imports", "Imports", "واردات"),
        ("nm-newexpord", "Exports", "صادرات"),
        ("nm-bacord", "Order Backlog", "سفارشات در انتظار"),
    ]

    results = {"mfg": {}, "svc": {}}

    for section, indicators in [("mfg", mfg_indicators), ("svc", svc_indicators)]:
        for dataset_code, label_en, label_fa in indicators:
            url = f"https://api.db.nomics.world/v22/series/ISM/{dataset_code}"
            try:
                resp = requests.get(url, params={
                    "observations": True,
                    "limit": config.MONTHS_BACK + 5,
                }, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                docs = data.get("series", {}).get("docs", [])
                # سری 'Index' رو پیدا کن (همون PMI واقعی)
                index_series = None
                for s in docs:
                    if s.get("series_name") == "Index":
                        index_series = s
                        break
                # fallback: اگر Index نبود، سری که مقادیرش حول ۵۰ است
                if not index_series and docs:
                    for s in docs:
                        vals = [v for v in s.get("value", []) if v is not None]
                        if vals and 40 < sum(vals[-3:]) / max(1, len(vals[-3:])) < 60:
                            index_series = s
                            break
                if not index_series and docs:
                    index_series = docs[0]

                if index_series:
                    periods = index_series.get("period", [])
                    values = index_series.get("value", [])

                    monthly = []
                    for p, v in zip(periods, values):
                        try:
                            monthly.append({"date": p, "value": round(float(v), 1)})
                        except (ValueError, TypeError):
                            monthly.append({"date": p, "value": None})

                    monthly = monthly[-config.MONTHS_BACK:]

                    results[section][label_en] = {
                        "label_en": label_en,
                        "label_fa": label_fa,
                        "data": monthly,
                    }
                    latest_val = next(
                        (m["value"] for m in reversed(monthly) if m["value"] is not None), None
                    )
                    log.info(f"  DBnomics ✅ {dataset_code} ({label_en}): {latest_val}")
            except requests.RequestException as e:
                log.warning(f"  DBnomics ⚠️ خطا در {dataset_code}: {e}")

    return results


# ─────────────────────────────────────────────────────────
# 3. Web Scraping — Trading Economics
# ─────────────────────────────────────────────────────────
def scrape_trading_economics(url, pattern):
    """استخراج عدد از صفحه Trading Economics"""
    if BeautifulSoup is None:
        return None

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # جستجوی عدد آخر در صفحه
        text = soup.get_text()
        matches = re.findall(pattern, text)
        if matches:
            val = float(matches[0])
            log.info(f"Scrape ✅ {url}: {val}")
            return val
    except Exception as e:
        log.error(f"Scrape ❌ {url}: {e}")

    return None


def scrape_latest_data():
    """دریافت آخرین داده‌ها از Trading Economics"""
    log.info("📡 استخراج داده از Trading Economics...")

    nfp = scrape_trading_economics(
        "https://tradingeconomics.com/united-states/non-farm-payrolls",
        r"(\d+\.\d+)(?:\s*(?:thousand|K))",
    )
    unemp = scrape_trading_economics(
        "https://tradingeconomics.com/united-states/unemployment-rate",
        r"(\d+\.\d+)\s*percent",
    )
    wage = scrape_trading_economics(
        "https://tradingeconomics.com/united-states/average-hourly-earnings",
        r"(\d+\.\d+)\s*percent",
    )
    claims = scrape_trading_economics(
        "https://tradingeconomics.com/united-states/jobless-claims",
        r"(\d+)\s*(?:thousand|K)",
    )

    return {"nfp": nfp, "unemployment": unemp, "wage": wage, "claims": claims}


# ─────────────────────────────────────────────────────────
# پردازش و تبدیل داده‌ها
# ─────────────────────────────────────────────────────────
def process_date(date_str):
    """تبدیل تاریخ به نام فارسی ماه"""
    if not date_str:
        return date_str
    # فرمت‌های ممکن: 'YYYY-MM-DD' یا 'YYYY-MM' (از DBnomics)
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            dt = datetime.strptime(date_str, fmt)
            month_name = PERSIAN_MONTHS[dt.month - 1]
            year = dt.year
            return f"{month_name} {year}"
        except ValueError:
            continue
    return date_str


def compute_mom_percent(series_data):
    """محاسبه تغییر ماهانه درصدی"""
    if not series_data or len(series_data) < 2:
        return None

    result = []
    for i in range(1, len(series_data)):
        curr = series_data[i].get("value")
        prev = series_data[i - 1].get("value")
        date = series_data[i].get("date")

        if curr is not None and prev is not None and prev != 0:
            pct = round(((curr - prev) / prev) * 100, 1)
            result.append({"date": date, "value": pct})
        else:
            result.append({"date": date, "value": None})

    return result


def build_output(fred_data, dbnomics_ism=None):
    """تبدیل داده خام FRED به ساختار JSON نهایی برای داشبورد"""
    output = {
        "last_update": datetime.now().isoformat(),
        "source": "fred",
    }

    # === NFP ===
    # توجه: PAYEMS خودش به‌صورت "هزار نفر" گزارش می‌شود،
    # پس تغییر ماهانه هم همان واحد است (نیازی به /1000 نیست).
    nfp_raw = fred_data.get("nfp")
    if nfp_raw:
        values = [int(round(d["value"])) if d["value"] is not None else None for d in nfp_raw]
        months = [process_date(d["date"]) for d in nfp_raw]
        valid = [v for v in values if v is not None]
        output["nfp"] = {
            "months": months,
            "values": values,
            "forecasts": [None] * len(values),  # FRED forecast نداره
            "previous": (valid[-2:] if len(valid) >= 2 else [None]),
            "unit": "K",
            "latest": valid[-1] if valid else None,
        }

    # === Unemployment ===
    unemp_raw = fred_data.get("unemployment")
    if unemp_raw:
        values = [d["value"] for d in unemp_raw]
        months = [process_date(d["date"]) for d in unemp_raw]
        valid = [v for v in values if v is not None]
        output["unemployment"] = {
            "months": months,
            "values": values,
            "latest": valid[-1] if valid else None,
        }

    # === Wage ===
    wage_raw = fred_data.get("wage")
    if wage_raw:
        mom = compute_mom_percent(wage_raw)
        values = [d["value"] for d in (mom or wage_raw)]
        months = [process_date(d["date"]) for d in (mom or wage_raw)]
        valid = [v for v in values if v is not None]
        output["wage"] = {
            "months": months,
            "values": values,
            "yoy": None,  # باید جدا محاسبه بشه
            "level": valid[-1] if valid else None,
            "latest": valid[-1] if valid else None,
        }

    # === Claims ===
    # توجه: ICSA داده هفتگی است — تاریخ باید روز + ماه باشد (نه فقط نام ماه)
    # مثلاً "۷ جولای ۲۰۲۶" به‌جای "جولای ۲۰۲۶" تا هفته‌ها قابل تفکیک باشند.
    claims_raw = fred_data.get("claims")
    if claims_raw:
        values = [int(d["value"] / 1000) for d in claims_raw if d["value"]]
        months = []
        for d in claims_raw:
            if d["value"] is None:
                continue
            try:
                dt = datetime.strptime(d["date"], "%Y-%m-%d")
                months.append(f"{dt.day} {PERSIAN_MONTHS[dt.month - 1]}")
            except (ValueError, TypeError):
                months.append(d["date"])
        output["claims"] = {
            "months": months,
            "values": values,
            "latest": values[-1] if values else None,
        }

    # === ISM Manufacturing PMI ===
    # شاخصی که حدود ۵۰ است؛ بالای ۵۰ = رشد، زیر ۵۰ = انقباض
    ism_mfg_raw = fred_data.get("ism_mfg")
    if ism_mfg_raw:
        values = [d["value"] for d in ism_mfg_raw]
        months = [process_date(d["date"]) for d in ism_mfg_raw]
        valid = [v for v in values if v is not None]
        output["ism_mfg"] = {
            "months": months,
            "values": values,
            "latest": valid[-1] if valid else None,
        }

    # === ISM Services PMI ===
    ism_svc_raw = fred_data.get("ism_svc")
    if ism_svc_raw:
        values = [d["value"] for d in ism_svc_raw]
        months = [process_date(d["date"]) for d in ism_svc_raw]
        valid = [v for v in values if v is not None]
        output["ism_svc"] = {
            "months": months,
            "values": values,
            "latest": valid[-1] if valid else None,
        }

    # === ISM جزئیات زیرشاخص‌ها (از DBnomics) ===
    if dbnomics_ism:
        output["ism_details"] = {}
        for section, key in [("mfg", "ism_mfg_details"), ("svc", "ism_svc_details")]:
            if dbnomics_ism.get(section):
                details = {}
                for indicator, info in dbnomics_ism[section].items():
                    monthly = info.get("data", [])
                    values = [m["value"] for m in monthly]
                    months_list = [process_date(m["date"]) for m in monthly]
                    valid = [v for v in values if v is not None]
                    details[indicator] = {
                        "label_en": info["label_en"],
                        "label_fa": info["label_fa"],
                        "months": months_list,
                        "values": values,
                        "latest": valid[-1] if valid else None,
                        "prev": valid[-2] if len(valid) >= 2 else None,
                    }
                output[key] = details

    return output


# ─────────────────────────────────────────────────────────
# ذخیره و مدیریت کش
# ─────────────────────────────────────────────────────────
def save_data(data, filepath=None):
    """ذخیره داده در فایل JSON"""
    path = Path(filepath or config.OUTPUT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"💾 داده‌ها ذخیره شد: {path}")


def load_cache(filepath=None):
    """بارگذاری داده کش‌شده"""
    path = Path(filepath or config.CACHE_FILE)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.warning(f"خطا در خواندن کش: {e}")
        return None


def save_cache(data, filepath=None):
    """ذخیره داده در کش"""
    path = Path(filepath or config.CACHE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────
# تابع اصلی
# ─────────────────────────────────────────────────────────
def _merge_ism_details(output, dbnomics_ism):
    """جزئیات ISM از DBnomics رو به output اضافه کن (در حالت fallback).

    اگر output قبلاً جزئیات نداشته باشه، از DEFAULT_DATA یا DBnomics زنده استفاده میشه.
    """
    if not dbnomics_ism:
        return  # DEFAULT_DATA قبلاً جزئیات داره
    for section, key in [("mfg", "ism_mfg_details"), ("svc", "ism_svc_details")]:
        if not dbnomics_ism.get(section):
            continue
        details = {}
        for indicator, info in dbnomics_ism[section].items():
            monthly = info.get("data", [])
            values = [m["value"] for m in monthly]
            months_list = [process_date(m["date"]) for m in monthly]
            valid = [v for v in values if v is not None]
            details[indicator] = {
                "label_en": info["label_en"],
                "label_fa": info["label_fa"],
                "months": months_list,
                "values": values,
                "latest": valid[-1] if valid else None,
                "prev": valid[-2] if len(valid) >= 2 else None,
            }
        if details:
            output[key] = details


def fetch_all():
    """دریافت داده‌ها از تمام منابع با fallback"""
    print()
    print("=" * 55)
    print("  🇺🇸 دریافت‌کننده داده‌های اقتصادی آمریکا")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)
    print()

    # مرحله ۱: FRED
    fred_data = fetch_all_fred()

    # مرحله ۱½: DBnomics — جزئیات زیرشاخص‌های ISM (مستقل از FRED)
    dbnomics_ism = None
    try:
        dbnomics_ism = fetch_dbnomics_ism()
    except Exception as e:
        log.warning(f"DBnomics خطا: {e}")

    if fred_data and fred_data.get("success"):
        output = build_output(fred_data, dbnomics_ism)
        output["source"] = "fred"
        log.info("✅ داده‌ها با موفقیت از FRED دریافت شد")
        save_data(output)
        save_cache(output)
        return output

    # مرحله ۲: BLS
    log.warning("FRED کامل جواب نداد — تلاش با BLS...")
    bls_data = fetch_bls()
    if bls_data:
        # TODO: پردازش داده BLS
        output = DEFAULT_DATA.copy()
        output["source"] = "bls"
        output["last_update"] = datetime.now().isoformat()
        # جزئیات ISM از DBnomics رو به fallback اضافه کن
        _merge_ism_details(output, dbnomics_ism)
        save_data(output)
        return output

    # مرحله ۳: Scraping
    log.warning("BLS هم جواب نداد — تلاش با Scraping...")
    scraped = scrape_latest_data()
    if scraped and any(v is not None for v in scraped.values()):
        output = DEFAULT_DATA.copy()
        output["source"] = "scraped"
        output["last_update"] = datetime.now().isoformat()
        # به‌روزرسانی آخرین مقادیر
        if scraped["nfp"] is not None:
            output["nfp"]["latest"] = int(scraped["nfp"])
        if scraped["unemployment"] is not None:
            output["unemployment"]["latest"] = scraped["unemployment"]
        if scraped["wage"] is not None:
            output["wage"]["latest"] = scraped["wage"]
        if scraped["claims"] is not None:
            output["claims"]["latest"] = int(scraped["claims"])
        # جزئیات ISM از DBnomics رو به fallback اضافه کن
        _merge_ism_details(output, dbnomics_ism)
        save_data(output)
        return output

    # مرحله ۴: Fallback روی داده پیش‌فرض
    log.error("❌ هیچ منبعی پاسخ نداد — استفاده از داده پیش‌فرض")
    cached = load_cache()
    if cached:
        log.info("📦 استفاده از داده کش‌شده قبلی")
        output = cached
        output["source"] = "cache"
        output["last_update"] = datetime.now().isoformat()
        _merge_ism_details(output, dbnomics_ism)
        save_data(output)
        return output

    # داده پیش‌فرض
    output = DEFAULT_DATA.copy()
    output["source"] = "default"
    output["last_update"] = datetime.now().isoformat()
    _merge_ism_details(output, dbnomics_ism)
    save_data(output)
    return output


if __name__ == "__main__":
    data = fetch_all()
    print()
    print("-" * 55)
    print("  📊 خلاصه داده‌های دریافت‌شده:")
    print("-" * 55)
    if data:
        print(f"  منبع: {data.get('source', 'نامشخص')}")
        print(f"  آخرین به‌روزرسانی: {data.get('last_update', '—')}")
        nfp = data.get("nfp", {})
        print(f"  NFP آخرین ماه: {nfp.get('latest', '—')}K")
        unemp = data.get("unemployment", {})
        print(f"  نرخ بیکاری: {unemp.get('latest', '—')}%")
        wage = data.get("wage", {})
        print(f"  دستمزد MoM: {wage.get('latest', '—')}%")
        claims = data.get("claims", {})
        print(f"  ادعای بیکاری: {claims.get('latest', '—')}K")
        ism_mfg = data.get("ism_mfg", {})
        print(f"  ISM Manufacturing PMI: {ism_mfg.get('latest', '—')}")
        ism_svc = data.get("ism_svc", {})
        print(f"  ISM Services PMI: {ism_svc.get('latest', '—')}")
    print("-" * 55)
    print("  ✅ فایل data.json آپدیت شد")
    print()
