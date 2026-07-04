# 🇺🇸 داشبورد اقتصاد آمریکا — خودکار

داشبورد تعاملی شاخص‌های کلیدی بازار کار آمریکا (NFP، نرخ بیکاری، دستمزد، ادعای بیکاری) که به‌صورت **هفتگی و خودکار** به‌روزرسانی می‌شود.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Status](https://img.shields.io/badge/Update-Weekly-green)

---

## ✨ ویژگی‌ها

- 📊 **۵ چارت تعاملی** (Chart.js) — NFP، بیکاری، دستمزد، Claims، رادار
- 📋 **جدول داده‌های ماهانه** با ارزیابی خودکار
- 💹 **تحلیل اثر بر بازارها** — دلار، طلا، سهام، اوراق
- 🧠 **سیگنال فدرال رزرو** — Dovish/Hawkish خودکار
- 🔄 **به‌روزرسانی خودکار** هفتگی با FRED/BLS API
- 📱 **واکنش‌گرا** و کاملاً فارسی (RTL)

---

## 🚀 نصب و راه‌اندازی

### ۱. نصب وابستگی‌ها
```bash
pip install -r requirements.txt
```

### ۲. (اختیاری) دریافت API Key رایگان
برای داده‌های دقیق و پایدار، یک API Key رایگان از FRED بگیرید:

1. به [fred.stlouisfed.org](https://fred.stlouisfed.org) ثبت‌نام کنید
2. به [این صفحه](https://fred.stlouisfed.org/myaccount/register/apikeys) بروید
3. API Key را در `config.py` قرار دهید:
   ```python
   FRED_API_KEY = "your_key_here"
   ```

> **بدون API Key هم کار می‌کند** — از BLS و Scraping استفاده می‌کند.

### ۳. اجرای دستی
```bash
python fetcher.py
```
سپس فایل `us-economy-dashboard.html` را در مرورگر باز کنید.

---

## 📁 ساختار پروژه

```
us-economy-dashboard/
├── us-economy-dashboard.html  # داشبورد اصلی (داینامیک)
├── fetcher.py                  # اسکریپت دریافت داده
├── config.py                   # تنظیمات API Keys
├── data.json                   # داده‌های دریافت‌شده (خروجی)
├── cache.json                  # کش داده‌ها (fallback)
├── deploy.ps1                  # اسکریپت دیپلوی PowerShell
├── requirements.txt            # وابستگی‌های پایتون
└── README.md
```

---

## ⏰ خودکارسازی هفتگی

### روش ۱: GitHub Actions (توصیه‌شده — ابری)
فایل `.github/workflows/update.yml` (در همین مخزن) هر هفته اجرا می‌شود.

### روش ۲: Windows Task Scheduler
در PowerShell با دسترسی ادمین:
```powershell
.\deploy.ps1
```

یا تنظیم دستی Task Scheduler برای اجرای `deploy.ps1` هر دوشنبه ساعت ۹ صبح.

---

## 🔌 منابع داده

| منبع | شاخص | نیاز به Key |
|------|------|-------------|
| [FRED API](https://fred.stlouisfed.org) | NFP، بیکاری، دستمزد، Claims | رایگان |
| [BLS API](https://www.bls.gov/developers) | تمام شاخص‌ها | اختیاری |
| [Trading Economics](https://tradingeconomics.com) | آخرین مقادیر (Scraping) | بدون Key |

اولویت: FRED → BLS → Scraping → داده کش‌شده → داده پیش‌فرض.

---

## 📜 توجه

این داشبورد صرفاً **جهت آموزش و تحلیل** است و **توصیه سرمایه‌گذاری محسوب نمی‌شود**.
