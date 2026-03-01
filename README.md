# 🌍 Geopolitical News Carousel Bot

An Instagram automation bot that posts a **10-slide geopolitical news carousel every 12 hours** — completely free, forever. No subscriptions, no paid tools.

---

## What It Does

- 🔍 **Researches** the top geopolitical story of the last 12 hours using Gemini + Google Search
- ✍️ **Writes** a professional 10-slide carousel: hook, context, players, stakes, ripple effects, statistics, scenarios, and a call to action
- 🎨 **Designs** all 10 slides as 1080×1080 JPG images with a branded dark/paper/red visual system
- ☁️ **Uploads** images to Cloudinary (free CDN)
- 📸 **Posts** the carousel to your Instagram page via Meta Graph API
- 📊 **Logs** every post to Google Sheets (optional)
- ⏰ **Runs automatically** at 06:00 and 18:00 Pakistan time via GitHub Actions

---

## Cost Breakdown

| Service | Free Tier | Monthly Cost |
|---|---|---|
| Google Gemini API | 1,500 requests/day | **$0** |
| Cloudinary | 25 GB storage, 25 GB bandwidth | **$0** |
| GitHub Actions | 2,000 minutes/month (~60 runs/month) | **$0** |
| Meta Graph API | Unlimited (rate limits apply) | **$0** |
| Google Sheets API | 500 req/100s per project | **$0** |
| **TOTAL** | | **$0/month** |

---

## Setup Guide

### Step 1 — Fork / Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/pakistan-news-bot.git
cd pakistan-news-bot
```

Push to your own GitHub repository.

---

### Step 2 — Get Your API Keys

#### A. Google Gemini API Key
1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API Key** → Select a Google Cloud project
3. Copy the key (starts with `AIza...`)

#### B. Cloudinary Credentials
1. Sign up free at [https://cloudinary.com/](https://cloudinary.com/)
2. Go to **Dashboard** → copy **Cloud Name**, **API Key**, **API Secret**

#### C. Instagram / Meta Graph API
1. Go to [https://developers.facebook.com/](https://developers.facebook.com/)
2. Create a new App → choose **Business** type
3. Add product: **Instagram Graph API**
4. Connect your Instagram Professional account (Business or Creator)
5. Generate a **long-lived Page Access Token** (valid 60 days — see note below)
6. Find your **Instagram User ID**:
   ```
   GET https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_TOKEN
   ```
   Use the `id` field of your Instagram-connected page, then:
   ```
   GET https://graph.facebook.com/v19.0/PAGE_ID?fields=instagram_business_account&access_token=YOUR_TOKEN
   ```

#### D. Google Sheets API (Optional)
1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a project → Enable **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** → Download JSON key
4. Create a new Google Sheet → copy the Sheet ID from the URL (the long string between `/d/` and `/edit`)
5. Share the sheet with the service account email (from the JSON key)

---

### Step 3 — Add GitHub Secrets

In your GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Where to Get It |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary Dashboard |
| `CLOUDINARY_API_KEY` | Cloudinary Dashboard |
| `CLOUDINARY_API_SECRET` | Cloudinary Dashboard |
| `INSTAGRAM_USER_ID` | Meta Graph API Explorer |
| `INSTAGRAM_ACCESS_TOKEN` | Meta Access Token Tool |
| `GOOGLE_SHEET_ID` | Google Sheets URL (optional) |
| `GOOGLE_CREDS_JSON` | Paste full service account JSON as string (optional) |

---

### Step 4 — Test Manually

1. Go to your repo → **Actions** tab
2. Select **Post Geopolitical Carousel**
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch the live logs

---

## Changing the Posting Schedule

Edit `.github/workflows/post.yml`, cron lines:

```yaml
- cron: "0 1 * * *"   # 01:00 UTC = 06:00 PKT
- cron: "0 13 * * *"  # 13:00 UTC = 18:00 PKT
```

Use [https://crontab.guru/](https://crontab.guru/) to calculate cron expressions for your timezone.

---

## Customising Brand Colors & Handle

Open `src/bot.py` and edit the constants at the top:

```python
C_DARK      = "#0e0c09"   # Cover background
C_RED       = "#c0392b"   # Accent / CTA color
C_PAPER     = "#f5f0e8"   # Body slide background
```

Change `@WORLDGEOPOLITICS` in the Gemini prompt and slide generation to your own Instagram handle.

---

## ⚠️ Instagram Token Expiry (Important!)

Instagram long-lived tokens expire after **60 days**. You must refresh manually:

1. Go to [https://developers.facebook.com/tools/explorer/](https://developers.facebook.com/tools/explorer/)
2. Generate a new long-lived token
3. Update your GitHub Secret `INSTAGRAM_ACCESS_TOKEN`

Set a calendar reminder every 50 days so you never miss it.

---

## Troubleshooting

### ❌ `JSONDecodeError` from Gemini
Gemini occasionally wraps JSON in markdown fences. The bot strips them automatically. If it still fails, check your Gemini API quota at [https://aistudio.google.com/](https://aistudio.google.com/).

### ❌ `Cloudinary upload failed`
- Check your free tier limits at [https://cloudinary.com/console](https://cloudinary.com/console)
- Verify `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` are correct

### ❌ `Failed to create container for slide N` (Instagram)
- Your access token may have expired — regenerate it (see above)
- Ensure your Instagram account is a **Professional** account (Business or Creator)
- Confirm the app has `instagram_content_publish` permission

### ❌ Font files missing / ugly text
The GitHub Actions workflow downloads fonts automatically. If you're running locally, download manually:
- [PlayfairDisplay-Bold.ttf](https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Bold.ttf)
- [SourceSerif4-Regular.ttf](https://github.com/google/fonts/raw/main/ofl/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf)

Place both files in the `fonts/` directory.

### ❌ Google Sheets not logging
This feature is optional and fails silently. Check:
- `GOOGLE_SHEET_ID` and `GOOGLE_CREDS_JSON` are both set
- Service account email has **Editor** access to the sheet
- Sheets API is enabled in your Google Cloud project

### ❌ GitHub Actions minutes running out
Each run takes ~3-5 minutes. 2 runs/day × 30 days = ~180–300 minutes/month, well within the 2,000-minute free tier.

---

## Running Locally

```bash
pip install -r requirements.txt

# Download fonts
mkdir -p fonts
curl -L "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Bold.ttf" -o fonts/PlayfairDisplay-Bold.ttf
curl -L "https://github.com/google/fonts/raw/main/ofl/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf" -o fonts/SourceSerif4-Regular.ttf

# Set environment variables
export GEMINI_API_KEY="..."
export CLOUDINARY_CLOUD_NAME="..."
export CLOUDINARY_API_KEY="..."
export CLOUDINARY_API_SECRET="..."
export INSTAGRAM_USER_ID="..."
export INSTAGRAM_ACCESS_TOKEN="..."

python src/bot.py
```

---

*Built with Python, Pillow, Google Gemini, Cloudinary, and Meta Graph API. 100% free forever.*
