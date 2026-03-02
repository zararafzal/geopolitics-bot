"""
Geopolitical News Carousel Bot
Researches top story, generates 10 slides, uploads to Cloudinary.
Instagram posting removed — slides saved locally and to Cloudinary.
"""

import os
import json
import time
import datetime
import cloudinary
import cloudinary.uploader
from PIL import Image, ImageDraw, ImageFont
from groq import Groq

# ─── CONFIG ──────────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
CLOUDINARY_CLOUD_NAME = os.environ["CLOUDINARY_CLOUD_NAME"]
CLOUDINARY_API_KEY    = os.environ["CLOUDINARY_API_KEY"]
CLOUDINARY_API_SECRET = os.environ["CLOUDINARY_API_SECRET"]
GOOGLE_SHEET_ID       = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CREDS_JSON     = os.environ.get("GOOGLE_CREDS_JSON", "")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# ─── COLORS & FONTS ──────────────────────────────────────────────────────────

C_DARK       = "#0e0c09"
C_RED        = "#c0392b"
C_PAPER      = "#f5f0e8"
C_WHITE      = "#ffffff"
C_GRAY_LIGHT = "#9b9b9b"
C_DARK_TEXT  = "#1a1a1a"
C_DARK_BAR   = "#1c1a17"

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")

def load_font(filename, size):
    path = os.path.join(FONT_DIR, filename)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        print(f"⚠️  Font {filename} not found, using default.")
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ─── GEMINI RESEARCH ─────────────────────────────────────────────────────────

GEMINI_PROMPT = """
You are a professional geopolitical analyst and Instagram content creator.

TASK: Search the web for the single most important geopolitical story from the last 12 hours.

SCORING — pick the story with the highest combined score:
- Global impact (0-10): How many countries / people are affected?
- Urgency (0-10): Is this breaking or developing right now?
- Clarity (0-10): Can a non-expert understand it in 30 seconds?
- Visual / data potential (0-10): Does it have compelling numbers or visuals?

Cover these categories:
- Wars, strikes, invasions, nuclear threats
- Elections, coups, leader assassinations or arrests
- Oil shocks, currency collapses, sanctions, debt crises
- Diplomatic ruptures, alliance shifts, UN emergency sessions
- Climate disasters that destabilise governments
- Tech or AI used as geopolitical weapons

Write 10 Instagram carousel slides with this EXACT structure:
- Slide 1  — Hook: alarming opening statement that forces a swipe
- Slide 2  — What happened: plain English, who did what to whom
- Slide 3  — The context: essential history in 2 sentences
- Slide 4  — The players: 3 key actors and what each wants
- Slide 5  — The stakes: what concretely could be won or lost
- Slide 6  — The global ripple: how it spreads to other countries
- Slide 7  — The number that shocks: one statistic that reframes everything
- Slide 8  — What happens next: best case and worst case scenario
- Slide 9  — What nobody is saying: the angle mainstream media misses
- Slide 10 — Call to action: why awareness matters, follow @WorldGeopolitics

RULES FOR COPY:
- Headlines: max 8 words, no full stop, punchy
- Body text: max 35 words, one idea only, no jargon, active voice
- Tone: urgent, clear, non-partisan, factual
- Write for a smart 25-year-old who doesn't follow the news

CAPTION: 120-150 words. Clean authoritative tone. No emojis in body.
End with: "Full breakdown in the carousel. Save this post."

HASHTAGS: 20-25 tags. Mix broad (#WorldNews #Geopolitics) and specific tags.
Always include #GeopoliticsDaily #FollowForUpdates.

RETURN ONLY a single valid JSON object. No markdown. No backticks. No explanation.
Exact structure:
{
  "topic": "5 word max topic name",
  "region": "primary region",
  "story_summary": "2-3 sentence internal summary",
  "urgency_score": 8,
  "slides": [
    {"slide_number": 1, "headline": "...", "body": "..."},
    {"slide_number": 2, "headline": "...", "body": "..."},
    {"slide_number": 3, "headline": "...", "body": "..."},
    {"slide_number": 4, "headline": "...", "body": "..."},
    {"slide_number": 5, "headline": "...", "body": "..."},
    {"slide_number": 6, "headline": "...", "body": "..."},
    {"slide_number": 7, "headline": "...", "body": "..."},
    {"slide_number": 8, "headline": "...", "body": "..."},
    {"slide_number": 9, "headline": "...", "body": "..."},
    {"slide_number": 10, "headline": "...", "body": "..."}
  ],
  "caption": "full 120-150 word caption here",
  "hashtags": "#WorldNews #Geopolitics ..."
}
"""

def fetch_content_from_gemini():
    print("🔍 Fetching top geopolitical story via Groq...")
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": GEMINI_PROMPT}],
            temperature=0.7,
            max_tokens=4000,
        )
        raw = completion.choices[0].message.content.strip()
        if not raw:
            raise RuntimeError("Groq returned empty response")
        print(f"📥 Groq raw response (first 300 chars): {raw[:300]}")
    except Exception as e:
        raise RuntimeError(f"Groq API call failed: {e}")

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parse error: {e}. Attempting cleanup...")
        last_brace = raw.rfind("}")
        if last_brace != -1:
            raw = raw[:last_brace+1]
        data = json.loads(raw)

    assert len(data["slides"]) == 10, "Expected exactly 10 slides"
    print(f"✅ Story selected: {data['topic']} | Urgency: {data['urgency_score']}/10")
    return data

# ─── IMAGE GENERATION ────────────────────────────────────────────────────────

SIZE = (1080, 1080)

def draw_wrapped_text(draw, text, font, x, y, max_width, fill, line_spacing=1.3):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_h = draw.textbbox((0, 0), "Ag", font=font)[3] - draw.textbbox((0, 0), "Ag", font=font)[1]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += int(line_h * line_spacing)
    return y

def make_slide_1(slide):
    img = Image.new("RGB", SIZE, hex_to_rgb(C_DARK))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (1080, 8)], fill=hex_to_rgb(C_RED))

    font_label    = load_font("SourceSerif4-Regular.ttf", 28)
    font_headline = load_font("PlayfairDisplay-Bold.ttf", 72)
    font_body     = load_font("SourceSerif4-Regular.ttf", 36)
    font_swipe    = load_font("SourceSerif4-Regular.ttf", 30)
    font_counter  = load_font("SourceSerif4-Regular.ttf", 26)

    draw.text((48, 36), "⚡ BREAKING NEWS", font=font_label, fill=hex_to_rgb(C_RED))
    draw_wrapped_text(draw, slide["headline"].upper(), font_headline,
                      48, 160, 984, hex_to_rgb(C_WHITE), line_spacing=1.2)
    draw_wrapped_text(draw, slide["body"], font_body,
                      48, 680, 984, hex_to_rgb(C_GRAY_LIGHT), line_spacing=1.4)
    draw.text((48, 980), "SWIPE TO READ →", font=font_swipe, fill=hex_to_rgb(C_RED))
    draw.text((1032, 980), "01/10", font=font_counter, fill=hex_to_rgb(C_GRAY_LIGHT))
    return img

def make_slide_body(slide, idx):
    img = Image.new("RGB", SIZE, hex_to_rgb(C_PAPER))
    draw = ImageDraw.Draw(img)

    font_handle   = load_font("SourceSerif4-Regular.ttf", 26)
    font_big_num  = load_font("PlayfairDisplay-Bold.ttf", 220)
    font_headline = load_font("PlayfairDisplay-Bold.ttf", 62)
    font_body     = load_font("SourceSerif4-Regular.ttf", 38)
    font_counter  = load_font("SourceSerif4-Regular.ttf", 26)

    draw.rectangle([(0, 0), (1080, 72)], fill=hex_to_rgb(C_DARK_BAR))
    draw.text((540, 36), "@WORLDGEOPOLITICS", font=font_handle,
              fill=hex_to_rgb(C_WHITE), anchor="mm")
    draw.text((20, 60), f"0{idx}", font=font_big_num, fill=(230, 224, 210))

    y = draw_wrapped_text(draw, slide["headline"], font_headline,
                          60, 340, 960, hex_to_rgb(C_DARK_TEXT), line_spacing=1.2)
    draw.rectangle([(60, y + 20), (200, y + 26)], fill=hex_to_rgb(C_RED))
    draw_wrapped_text(draw, slide["body"], font_body,
                      60, y + 60, 960, (80, 72, 60), line_spacing=1.5)

    draw.rectangle([(0, 1072), (1080, 1080)], fill=hex_to_rgb(C_RED))
    draw.text((1032, 1042), f"{idx:02d}/10", font=font_counter, fill=hex_to_rgb(C_WHITE))
    return img

def make_slide_10(slide):
    img = Image.new("RGB", SIZE, hex_to_rgb(C_RED))
    draw = ImageDraw.Draw(img)

    font_headline = load_font("PlayfairDisplay-Bold.ttf", 72)
    font_body     = load_font("SourceSerif4-Regular.ttf", 40)
    font_follow   = load_font("SourceSerif4-Regular.ttf", 34)

    draw.rectangle([(0, 0), (1080, 12)], fill=hex_to_rgb(C_DARK))
    y = draw_wrapped_text(draw, slide["headline"].upper(), font_headline,
                          60, 160, 960, hex_to_rgb(C_WHITE), line_spacing=1.2)
    draw_wrapped_text(draw, slide["body"], font_body,
                      60, y + 60, 960, hex_to_rgb(C_WHITE), line_spacing=1.5)
    draw.rectangle([(0, 880), (1080, 1080)], fill=hex_to_rgb(C_DARK))
    draw.text((540, 980), "FOLLOW @WORLDGEOPOLITICS FOR UPDATES",
              font=font_follow, fill=hex_to_rgb(C_WHITE), anchor="mm")
    return img

def generate_slides(data):
    print("🎨 Generating slide images...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    images = []
    paths  = []
    for slide in data["slides"]:
        n = slide["slide_number"]
        if n == 1:
            img = make_slide_1(slide)
        elif n == 10:
            img = make_slide_10(slide)
        else:
            img = make_slide_body(slide, n)

        path = os.path.join(OUTPUT_DIR, f"slide_{n:02d}.jpg")
        img.save(path, "JPEG", quality=92)
        images.append(img)
        paths.append(path)
        print(f"  ✅ Slide {n} saved → {path}")
    return images, paths

# ─── CLOUDINARY UPLOAD ───────────────────────────────────────────────────────

def upload_to_cloudinary(paths, topic):
    print("☁️  Uploading images to Cloudinary...")
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    urls = []
    slug = topic.lower().replace(" ", "_")[:30]
    ts   = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M")

    for i, path in enumerate(paths):
        public_id = f"geopolitics/{slug}_{ts}_slide_{i+1:02d}"
        try:
            result = cloudinary.uploader.upload(
                path,
                public_id=public_id,
                overwrite=True,
                resource_type="image"
            )
            url = result["secure_url"]
            urls.append(url)
            print(f"  ✅ Slide {i+1} uploaded: {url}")
        except Exception as e:
            raise RuntimeError(f"Cloudinary upload failed for slide {i+1}: {e}")
    return urls

# ─── GOOGLE SHEETS LOGGING ───────────────────────────────────────────────────

def log_to_google_sheets(data, image_urls):
    if not GOOGLE_CREDS_JSON or not GOOGLE_SHEET_ID:
        print("⚠️  Google Sheets env vars not set — skipping log.")
        return
    print("📊 Logging to Google Sheets...")
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(GOOGLE_SHEET_ID).sheet1

        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        row = [
            timestamp,
            data["topic"],
            data["region"],
            data["story_summary"][:200],
            data["caption"][:200],
            image_urls[0] if image_urls else "N/A",
            "✅ Generated"
        ]
        sheet.append_row(row)
        print("  ✅ Logged to Google Sheets")
    except Exception as e:
        print(f"  ⚠️  Google Sheets logging failed (non-fatal): {e}")

# ─── SAVE CAPTION & HASHTAGS ─────────────────────────────────────────────────

def save_caption(data):
    path = os.path.join(OUTPUT_DIR, "caption.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("=== TOPIC ===\n")
        f.write(data["topic"] + "\n\n")
        f.write("=== CAPTION ===\n")
        f.write(data["caption"] + "\n\n")
        f.write("=== HASHTAGS ===\n")
        f.write(data["hashtags"] + "\n\n")
        f.write("=== STORY SUMMARY ===\n")
        f.write(data["story_summary"] + "\n")
    print(f"📝 Caption saved → {path}")

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🌍 GEOPOLITICS BOT — STARTING RUN")
    print(f"🕐 UTC: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. Research + write content
    data = fetch_content_from_gemini()

    # 2. Generate + save slides locally
    images, paths = generate_slides(data)

    # 3. Upload to Cloudinary
    image_urls = upload_to_cloudinary(paths, data["topic"])

    # 4. Save caption and hashtags to text file
    save_caption(data)

    # 5. Log to Google Sheets (optional)
    log_to_google_sheets(data, image_urls)

    print("=" * 60)
    print(f"🎉 SUCCESS")
    print(f"📰 Topic: {data['topic']}")
    print(f"🌏 Region: {data['region']}")
    print(f"🖼️  Slides saved to: {OUTPUT_DIR}")
    print(f"☁️  Cloudinary URLs:")
    for i, url in enumerate(image_urls):
        print(f"   Slide {i+1}: {url}")
    print("=" * 60)

if __name__ == "__main__":
    main()
