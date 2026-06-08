# 🕌 بوت أذاني — Adhani Prayer Times Bot

بوت تيليغرام احترافي لأوقات الصلاة، يتميز بدقته العالية وسرعته الفائقة في التعامل مع أعداد كبيرة من المستخدمين، مع دعم كامل للغة العربية والإنجليزية.

A professional Telegram bot for Islamic prayer times, high performance, sharded database support, and full Arabic/English localization.

---

## 🚀 المميزات | Features

- **🌍 تحديد تلقائي للموقع | Auto-location**: دعم GPS وإرسال الموقع أو اختيار يدوي للمدينة. | Support for GPS, live location, or manual city selection.
- **🔔 نظام تذكيرات ذكي | Smart Reminders**: محرك تذكيرات مُحسن يدعم حتى 500ألف مستخدم مع معالجة على دُفعات لتجنب حظر تيليغرام. | Optimized reminder engine supporting up to 500k users with batch processing to avoid Telegram rate limits.
- **🗄️ قاعدة بيانات مجزأة (Sharding) | Sharded Database**: توزيع المستخدمين على عدة ملفات SQLite لزيادة كفاءة القراءة والكتابة والنسخ الاحتياطي. | Distributing users across multiple SQLite files for better I/O performance and easier backups.
- **🔄 ترحيل تلقائي | Auto Migration**: نظام تحويل تلقائي لقواعد البيانات القديمة إلى الصيغة الحديثة. | Automatic migration system from legacy database formats to the current sharded schema.
- **🛠️ لوحة تحكم إدارية | Admin Panel**: واجهة متكاملة للمالك لإدارة الإحصائيات وإرسال الرسائل الجماعية. | Comprehensive dashboard for the owner to manage stats and global broadcasts.
- **💬 تفاعل ذكي | Smart Interaction**: الاستجابة لكلمات مفتاحية مثل "أذاني" أو "الصلاة" تلقائياً. | Automatic response to keywords like "Adhani" or "Prayer".

---

## 📁 هيكل المشروع | Project Structure

```text
Adhani-Prayer-Bot/
├── main.py                  # نقطة الدخول الرئيسية | Main entry point
├── config.py                # الإعدادات المركزية | Central configuration
├── requirements.txt         # المكتبات المطلوبة | Dependencies
├── test_bot.py              # ملف الاختبارات | Test suite
├── .env                     # متغيرات البيئة | Environment variables
│
├── services/                # الخدمات الأساسية | Core services
│   ├── database.py          # إدارة البيانات (Sharding & Migrations) | Database Management
│   ├── prayer.py            # جلب أوقات الصلاة ومعالجتها | Prayer time fetching
│   ├── geo.py               # خدمات الموقع الجغرافي | Geolocation services
│   └── reminders.py         # محرك التذكيرات المجدولة | Scheduled reminders engine
│
├── handlers/                # معالجات الأوامر | Command handlers
│   ├── start.py             # البداية واختيار المدينة | Start & City selection
│   ├── prayer_cmds.py       # أوامر الصلاة والكلمات المفتاحية | Prayer commands & Keywords
│   ├── settings.py          # لوحة إعدادات المستخدم | User settings panel
│   ├── admin.py             # لوحة تحكم المشرف والرسائل الجماعية | Admin panel & Broadcasts
│   ├── group.py             # إعدادات المجموعات | Group settings
│   ├── reminder_cmd.py      # إدارة التنبيهات | Reminder management
│   └── keyboards.py         # واجهات المستخدم (GUI) | User Interfaces
│
├── utils/                   # الأدوات المساعدة | Utilities
│   ├── i18n.py              # نظام اللغات (Arabic/English) | Localization system
│   ├── logger.py            # نظام تتبع السجلات | Logging system
│   └── helpers.py           # دوال مساعدة عامة | General helper functions
│
├── storage/                 # مخزن قواعد البيانات | SQLite Database Shards
└── logs/                    # سجلات التشغيل | Operational Logs
```

---

## 🛠️ الأوامر المدعومة | Supported Commands

### 👤 للمستخدمين | User Commands
| الأمر | الوصف (العربية) | Description (English) |
|-------|-----------------|-----------------------|
| `/start` | بدء البوت واختيار المدينة | Start bot & set city |
| `/a` | عرض وقت الصلاة القادم | Get next prayer time |
| `/schedule` | جدول أوقات الصلاة لليوم | Today's prayer schedule |
| `/reminder` | إدارة تنبيهات الصلاة | Manage prayer reminders |
| `/my` | لوحة إعدادات المستخدم | User settings panel |
| `/g` | إعدادات المجموعة | Group settings |
| `/help` | عرض تعليمات المساعدة | Show help instructions |
| `أذاني` | مشغل الكلمات المفتاحية | Trigger next prayer info |

### 👑 للمشرفين | Admin Commands
- `/admin`: لوحة التحكم الكاملة | Main control panel.
- `/stats`: إحصائيات الاستخدام | Bot statistics.
- `/broadcast`: إرسال رسالة جماعية لجميع المستخدمين | Global broadcast.

---

## ⚙️ الإعدادات | Configuration (.env)

| المتغير | الوصف | Description | المثال |
|---------|-------|-------------|--------|
| `TELEGRAM_TOKEN` | توكن البوت من BotFather | Bot token from BotFather | `123456:ABC...` |
| `WEBHOOK_URL` | رابط الويب هوك (Polling اتركه فارغاً لـ) | Webhook URL (Leave empty for Polling) | `https://yourdomain.com` |
| `WEBHOOK_SECRET` | سر للأمان (يتم توليده تلقائياً إن لم يوجد) | Security secret (auto-generated if missing) | `random_secret_string` |
| `PORT` | منفذ الخادم (uvicorn الارتباط بـ) | Server port (linked to uvicorn) | `8000` |
| `ADMIN_ID` | معرّفك الرقمي في تيليغرام | Your Telegram user ID | `716300112` |
| `ALLOWED_COUNTRIES` | (ISO 3166-1 alpha-2) أكواد الدول المسموحة | Allowed country codes (ISO alpha-2) | `SA,KW,AE` |
| `ALADHAN_API_URL` | جلب أوقات الصلاة API رابط | API URL for fetching prayer times | `https://api.aladhan.com/v1/timings` |
| `REMINDER_BATCH_SIZE` | عدد التذكيرات التي يتم فحصها دفعة واحدة | Number of reminders processed in one batch | `50` |

---

## 🚀 التثبيت والتشغيل | Installation & Setup

### 1. المتطلبات | Requirements
- Python 3.10+
- بيئة افتراضية (مستحسن) | Virtual Environment (Recommended)
- توكن بوت من [@BotFather](https://t.me/BotFather) | Bot Token from BotFather

### 2. التثبيت | Installation
```bash
git clone https://github.com/iH4xz/Adhani.git
cd Adhani
python -m venv venv
source venv/Scripts/activate  # لنظام ويندوز | Windows
# source venv/bin/activate    # لنظام لينكس | Linux
pip install -r requirements.txt
```

### 3. الإعداد | Configuration
قم بنسخ ملف `.env.example` إلى `.env` واملأ البيانات اللازمة.  
Copy `.env.example` to `.env` and fill in the required variables.

### 4. التشغيل | Execution
البوت يدعم طريقتين للتشغيل تلقائياً:  
The bot automatically detects and supports two running modes:

**A. وضع Polling (للتطوير) | Polling Mode (Development):**
```bash
python main.py
```

**B. وضع Webhook (للإنتاج) | Webhook Mode (Production):**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🗄️ نظام قواعد البيانات | Database Management

يستخدم البوت معمارية **Sharded SQLite** لضمان استقرار الأداء:  
The bot utilizes a **Sharded SQLite** architecture for high performance:

- يتم تقسيم المستخدمين كل 100 مستخدم في ملف قاعدة بيانات منفصل (`users_shard_X.db`).  
  Users are split into separate database shards every 100 users.
- يتم الانتقال التلقائي من نظام النسخة القديمة (`.sqlite`) إلى النسخة الحديثة (`.db`) فور التشغيل.  
  Automatic transition from legacy versions (`.sqlite`) to current format (`.db`) on startup.
- يتم تفعيل نمط **WAL (Write-Ahead Logging)** لضمان سرعة الوصول المتزامن.  
  **WAL (Write-Ahead Logging)** mode is enabled for faster concurrent access.

---

## 🛠️ التقنيات | Technologies

- **Python-Telegram-Bot (v22.6)**: أحدث إصدار لمكتبة تيليغرام. | Latest Telegram library version.
- **FastAPI & Uvicorn**: خادم ويب عالي الأداء لمعالجة الويب هوك. | High-performance web server for webhooks.
- **aiosqlite**: للتعامل غير المتزامن مع قواعد البيانات. | Asynchronous SQLite interaction.
- **HTTPX**: لإرسال طلبات الـ API بسرعة وكفاءة. | Fast and efficient asynchronous API requests.
- **Geopy & Timezonefinder**: للتعامل مع المواقع الجغرافية والمناطق الزمنية. | Geolocation and timezone management.

---

## 📜 الترخيص | License

هذا المشروع متاح للاستخدام المفتوح.
This project is open-source.
