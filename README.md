# 🕌 بوت أذاني — Adhani Prayer Times Bot

بوت تيليغرام احترافي لأوقات الصلاة، يتميز بدقته العالية وسرعته الفائقة في التعامل مع أعداد كبيرة من المستخدمين، مع دعم كامل للغة العربية والإنجليزية.

A professional Telegram bot for Islamic prayer times, high performance, sharded database support, and full Arabic/English localization.

---

## 🚀 المميزات | Features

- **🌍 تحديد تلقائي للموقع**: دعم GPS وإرسال الموقع أو اختيار يدوي للمدينة.
- **🔔 نظام تذكيرات ذكي**: محرك تذكيرات مُحسن يدعم حتى 500ألف مستخدم مع معالجة على دُفعات لتجنب حظر تيليغرام.
- **🗄️ قاعدة بيانات مجزأة (Sharding)**: توزيع المستخدمين على عدة ملفات SQLite لزيادة كفاءة القراءة والكتابة والنسخ الاحتياطي.
- **🔄 ترحيل تلقائي**: نظام تحويل تلقائي لقواعد البيانات القديمة إلى الصيغة الحديثة.
- **🛠️ لوحة تحكم إدارية**: واجهة متكاملة للمالك لإدارة الإحصائيات وإرسال الرسائل الجماعية.
- **💬 تفاعل ذكي**: الاستجابة لكلمات مفتاحية مثل "أذاني" أو "الصلاة" تلقائياً.

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
│   ├── database.py          # إدارة البيانات (Sharding & Migrations)
│   ├── prayer.py            # جلب أوقات الصلاة ومعالجتها
│   ├── geo.py               # خدمات الموقع الجغرافي
│   └── reminders.py         # محرك التذكيرات المجدولة
│
├── handlers/                # معالجات الأوامر | Command handlers
│   ├── start.py             # البداية واختيار المدينة
│   ├── prayer_cmds.py       # أوامر الصلاة والكلمات المفتاحية
│   ├── settings.py          # لوحة إعدادات المستخدم
│   ├── admin.py             # لوحة تحكم المشرف والرسائل الجماعية
│   ├── group.py             # إعدادات المجموعات
│   ├── reminder_cmd.py      # إدارة التنبيهات
│   └── keyboards.py         # واجهات المستخدم (GUI)
│
├── utils/                   # الأدوات المساعدة | Utilities
│   ├── i18n.py              # نظام اللغات (Arabic/English)
│   ├── logger.py            # نظام تتبع السجلات
│   └── helpers.py           # دوال مساعدة عامة
│
├── storage/                 # مخزن قواعد البيانات | SQLite Shards
└── logs/                    # سجلات التشغيل | Deployment logs
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

| المتغير | الوصف | المثال |
|---------|-------|--------|
| `TELEGRAM_TOKEN` | توكن البوت من BotFather | `123456:ABC...` |
| `WEBHOOK_URL` | رابط الويب هوك (اتركه فارغاً لوضع Polling) | `https://yourdomain.com` |
| `WEBHOOK_SECRET` | سر للأمان (يتم توليده تلقائياً إن لم يوجد) | `random_secret_string` |
| `PORT` | منفذ الخادم (الارتباط بـ uvicorn) | `8000` |
| `ADMIN_ID` | معرّفك الرقمي في تيليغرام | `716300112` |
| `ALLOWED_COUNTRIES` | أكواد الدول المسموحة (ISO 3166-1 alpha-2) | `SA,KW,AE` |
| `ALADHAN_API_URL` | رابط API لجلب أوقات الصلاة | `https://api.aladhan.com/v1/timings` |
| `REMINDER_BATCH_SIZE` | عدد التذكيرات التي يتم فحصها دفعة واحدة | `50` |

---

## 🚀 التثبيت والتشغيل | Installation & Setup

### 1. المتطلبات
- Python 3.10+
- بيئة افتراضية (مستحسن)
- توكن بوت من [@BotFather](https://t.me/BotFather)

### 2. التثبيت
```bash
git clone https://github.com/iH4xz/Adhani.git
cd Adhani-Prayer-Bot
python -m venv venv
source venv/Scripts/activate  # لنظام ويندوز
# source venv/bin/activate    # لنظام لينكس
pip install -r requirements.txt
```

### 3. الإعداد
قم بنسخ ملف `.env.example` إلى `.env` واملأ البيانات اللازمة.

### 4. التشغيل
البوت يدعم طريقتين للتشغيل تلقائياً:

**A. وضع Polling (للتطوير):**
```bash
python main.py
```

**B. وضع Webhook (للإنتاج):**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🗄️ نظام قواعد البيانات | Database Management

يستخدم البوت معمارية **Sharded SQLite** لضمان استقرار الأداء:
- يتم تقسيم المستخدمين كل 100 مستخدم في ملف قاعدة بيانات منفصل (`users_shard_X.db`).
- يتم الانتقال التلقائي من نظام النسخة القديمة (`.sqlite`) إلى النسخة الحديثة (`.db`) فور التشغيل.
- يتم تفعيل نمط **WAL (Write-Ahead Logging)** لضمان سرعة الوصول المتزامن.

---

## 🛠️ التقنيات | Technologies

- **Python-Telegram-Bot (v22.6)**: أحدث إصدار لمكتبة تيليغرام.
- **FastAPI & Uvicorn**: خادم ويب عالي الأداء لمعالجة الويب هوك.
- **aiosqlite**: للتعامل غير المتزامن مع قواعد البيانات.
- **HTTPX**: لإرسال طلبات الـ API بسرعة وكفاءة.
- **Geopy & Timezonefinder**: للتعامل مع المواقع الجغرافية والمناطق الزمنية.

---

## 📜 الترخيص | License

هذا المشروع متاح للاستخدام المفتوح.
This project is open-source.
