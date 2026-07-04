<#
.SYNOPSIS
  اسکریپت دیپلوی داشبورد اقتصاد آمریکا
.DESCRIPTION
  1. داده‌های جدید را از اینترنت دریافت می‌کند (fetcher.py)
  2. تغییرات را در گیت کامیت و پوش می‌کند
  3. GitHub Pages به‌صورت خودکار آپدیت می‌شود
#>

param(
    [string]$CommitMsg = "chore: weekly data update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  🚀 شروع فرآیند دیپلوی داشبورد" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── مرحله ۱: اجرای fetcher.py ───
Write-Host "[1/4] 📊 دریافت داده‌های اقتصادی..." -ForegroundColor Yellow
python fetcher.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ خطا در اجرای fetcher.py" -ForegroundColor Red
    exit 1
}
Write-Host "✅ داده‌ها با موفقیت دریافت شدند" -ForegroundColor Green
Write-Host ""

# ─── مرحله ۲: بررسی گیت ───
Write-Host "[2/4] 📝 بررسی تغییرات گیت..." -ForegroundColor Yellow
if (-not (Test-Path ".git")) {
    Write-Host "⚠️  مخزن گیت موجود نیست — اجرای git init..." -ForegroundColor Yellow
    git init
    git branch -M main
}

$hasChanges = git status --porcelain
if (-not $hasChanges) {
    Write-Host "ℹ️  تغییری برای کامیت وجود ندارد" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  ✅ تمام شد — تغییری لازم نبود" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    exit 0
}

# ─── مرحله ۳: کامیت ───
Write-Host "[3/4] 📦 کامیت تغییرات..." -ForegroundColor Yellow
git add -A
git commit -m $CommitMsg
Write-Host "✅ تغییرات کامیت شد" -ForegroundColor Green
Write-Host ""

# ─── مرحله ۴: پوش ───
Write-Host "[4/4] 📤 ارسال به GitHub..." -ForegroundColor Yellow
$hasRemote = git remote get-url origin 2>$null
if (-not $hasRemote) {
    Write-Host "⚠️  ریموت تنظیم نشده!" -ForegroundColor Red
    Write-Host "   ابتدا یک مخزن در GitHub بسازید و سپس:" -ForegroundColor Yellow
    Write-Host "   git remote add origin https://github.com/USERNAME/us-economy-dashboard.git" -ForegroundColor Yellow
    Write-Host "   git push -u origin main" -ForegroundColor Yellow
    exit 1
}

git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ خطا در push — اعتبار گیت را بررسی کنید" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ دیپلوی موفقیت‌آمیز بود!" -ForegroundColor Green
Write-Host "  🌐 داشبورد در چند دقیقه آپدیت می‌شود" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
