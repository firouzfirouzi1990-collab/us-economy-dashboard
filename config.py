"""
تنظیمات داشبورد اقتصاد آمریکا — US Economic Dashboard
======================================================

برای استفاده از FRED API:
1. به https://fred.stlouisfed.org/myaccount/register/apikeys بروید
2. ثبت‌نام رایگان کنید
3. API Key خود را در فیلد زیر قرار دهید

بدون API Key هم اسکریپت کار می‌کند — از منابع دیگر استفاده می‌کند.
"""

import os

# FRED API Key (رایگان از https://fred.stlouisfed.org)
# ⚠️ ایمنی: کلید را هرگز در کد قرار ندهید!
#   - محلی:  متغیر محیطی FRED_API_KEY را تنظیم کنید
#   - GitHub: در Settings → Secrets → Actions اضافه کنید
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# BLS API Key (رایگان از https://www.bls.gov/developers)
BLS_API_KEY = os.environ.get("BLS_API_KEY", "")

# مسیر فایل خروجی
OUTPUT_FILE = "data.json"

# مسیر فایل کش (وقتی API در دسترس نیست)
CACHE_FILE = "cache.json"

# محدوده داده‌ها — چند ماه اخیر
MONTHS_BACK = 8

# شناسه سری‌های FRED
FRED_SERIES = {
    "nfp": "PAYEMS",           # Non-Farm Payrolls (Total level)
    "unemployment": "UNRATE",  # Unemployment Rate
    "wage": "CES0500000003",   # Average Hourly Earnings
    "claims": "ICSA",          # Initial Jobless Claims
    "ism_mfg": "NAPM",         # ISM Manufacturing PMI (شاخص حول ۵۰)
    "ism_svc": "NAPMS",        # ISM Services PMI / Non-Manufacturing
}

# تنظیمات لاگ
LOG_LEVEL = "INFO"
