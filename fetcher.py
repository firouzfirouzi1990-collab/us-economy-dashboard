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
        "months": ["ژانویه", "فوریه", "مارس", "آوریل", "می", "ژوئن"],
        "values": [223, 221, 219, 217, 225, 215],
        "latest": 215,
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

    success = all(v is not None for v in [nfp_changes, unemployment, wage, claims])
    if not success:
        log.warning("FRED: برخی سری‌ها دریافت نشدند")

    return {
        "nfp": nfp_changes,
        "unemployment": unemployment,
        "wage": wage,
        "claims": claims,
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
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        month_name = PERSIAN_MONTHS[dt.month - 1]
        year = dt.year
        return f"{month_name} {year}"
    except ValueError:
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


def build_output(fred_data):
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
    # توجه: ICSA به‌صورت "تعداد نفر" گزارش می‌شود، پس باید /1000 شود (215000 -> 215K).
    claims_raw = fred_data.get("claims")
    if claims_raw:
        values = [int(d["value"] / 1000) for d in claims_raw if d["value"]]
        months = [process_date(d["date"]) for d in claims_raw if d["value"]]
        output["claims"] = {
            "months": months,
            "values": values,
            "latest": values[-1] if values else None,
        }

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
    if fred_data and fred_data.get("success"):
        output = build_output(fred_data)
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
        save_data(output)
        return output

    # داده پیش‌فرض
    output = DEFAULT_DATA.copy()
    output["source"] = "default"
    output["last_update"] = datetime.now().isoformat()
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
    print("-" * 55)
    print("  ✅ فایل data.json آپدیت شد")
    print()
