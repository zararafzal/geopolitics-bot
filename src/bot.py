"""
Instagram Geopolitical News Carousel Bot
Runs every 12 hours via GitHub Actions
"""

import os
import json
import time
import textwrap
import datetime
import requests
import cloudinary
import cloudinary.uploader
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

# ─── CONFIG ──────────────────────────────────────────────────────────────────

GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
CLOUDINARY_CLOUD_NAME = os.environ["CLOUDINARY_CLOUD_NAME"]
CLOUDINARY_API_KEY    = os.environ["CLOUDINARY_API_KEY"]
CLOUDINARY_API_SECRET = os.environ["CLOUDINARY_API_SECRET"]
INSTAGRAM_USER_ID     = os.environ["INSTAGRAM_USER_ID"]
INSTAGRAM_ACCESS_TOKEN= os.environ["INSTAGRAM_ACCESS_TOKEN"]
GOOGLE_SHEET_ID       = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CREDS_JSON     = os.environ.get("GOOGLE_CREDS_JSON", "")

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE        = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# ─── COLORS & FONTS ──────────────────────────────────────────────────────────

C_DARK      = "#0e0c09"
C_RED       = "#c0392b"
C_PAPER     = "#f5f0e8"
C_WHITE     = "#ffffff"
C_GRAY_LIGHT= "#9b9b9b"
C_DARK_TEXT = "#1a1a1a"
C_DARK_BAR  = "#1c1a17"

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")

def load_font(filename, size):
    path = os.path.join(FONT_DIR, filename)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        print(f"⚠️  Font {filename} not found, using default.")
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
- Slide 1  — Hook: alarming opening statement that forces a swipe. No full stop.
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

HASHTAGS: 20-25 tags. Mix broad (#WorldNews #Geopolitics) and specific
(#CountryName #TopicName #LeaderName). Always include #GeopoliticsDaily #FollowForUpdates.

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
    print("🔍 Fetching top geopolitical story from Gemini...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools="google_search_retrieval"
    )
    try:
        response = model.generate_content(GEMINI_PROMPT)
        raw = response.text.strip()
        print(f"📥 Gemini raw response (first 300 chars): {raw[:300]}")
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")

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
        # Remove any trailing content after last }
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
    """Draw wrapped text and return the y position after the last line."""
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
    """Cover slide — dark background."""
    img = Image.new("RGB", SIZE, hex_to_rgb(C_DARK))
    draw = ImageDraw.Draw(img)

    # Top red bar
    draw.rectangle([(0, 0), (1080, 8)], fill=hex_to_rgb(C_RED))

    # BREAKING NEWS label
    font_label = load_font("SourceSerif4-Regular.ttf", 28)
    draw.text((48, 36), "⚡ BREAKING NEWS", font=font_label, fill=hex_to_rgb(C_RED))

    # Headline
    font_headline = load_font("PlayfairDisplay-Bold.ttf", 72)
    draw_wrapped_text(draw, slide["headline"].upper(), font_headline,
                      48, 160, 984, hex_to_rgb(C_WHITE), line_spacing=1.2)

    # Body subtext
    font_body = load_font("SourceSerif4-Regular.ttf", 36)
    draw_wrapped_text(draw, slide["body"], font_body,
                      48, 680, 984, hex_to_rgb(C_GRAY_LIGHT), line_spacing=1.4)

    # SWIPE CTA
    font_swipe = load_font("SourceSerif4-Regular.ttf", 30)
    draw.text((48, 980), "SWIPE TO READ →", font=font_swipe, fill=hex_to_rgb(C_RED))

    # Slide counter
    font_counter = load_font("SourceSerif4-Regular.ttf", 26)
    draw.text((990, 980), "01/10", font=font_counter, fill=hex_to_rgb(C_GRAY_LIGHT), anchor="ra")

    return img

def make_slide_body(slide, idx):
    """Body slides 2-9 — warm paper background."""
    img = Image.new("RGB", SIZE, hex_to_rgb(C_PAPER))
    draw = ImageDraw.Draw(img)

    # Top dark bar
    draw.rectangle([(0, 0), (1080, 72)], fill=hex_to_rgb(C_DARK_BAR))
    font_handle = load_font("SourceSerif4-Regular.ttf", 26)
    draw.text((540, 36), "@WORLDGEOPOLITICS", font=font_handle,
              fill=hex_to_rgb(C_WHITE), anchor="mm")

    # Decorative large slide number
    font_big_num = load_font("PlayfairDisplay-Bold.ttf", 220)
    draw.text((20, 60), f"0{idx}", font=font_big_num,
              fill=(230, 224, 210))  # very light on paper

    # Headline
    font_headline = load_font("PlayfairDisplay-Bold.ttf", 62)
    y = draw_wrapped_text(draw, slide["headline"], font_headline,
                          60, 340, 960, hex_to_rgb(C_DARK_TEXT), line_spacing=1.2)

    # Red divider
    draw.rectangle([(60, y + 20), (200, y + 26)], fill=hex_to_rgb(C_RED))

    # Body text
    font_body = load_font("SourceSerif4-Regular.ttf", 38)
    draw_wrapped_text(draw, slide["body"], font_body,
                      60, y + 60, 960, (80, 72, 60), line_spacing=1.5)

    # Bottom red bar
    draw.rectangle([(0, 1072), (1080, 1080)], fill=hex_to_rgb(C_RED))

    # Slide counter
    font_counter = load_font("SourceSerif4-Regular.ttf", 26)
    num_str = f"{idx:02d}/10"
    draw.text((1032, 1042), num_str, font=font_counter,
              fill=hex_to_rgb(C_WHITE), anchor="ra")

    return img

def make_slide_10(slide):
    """CTA slide — red background."""
    img = Image.new("RGB", SIZE, hex_to_rgb(C_RED))
    draw = ImageDraw.Draw(img)

    # Dark top bar
    draw.rectangle([(0, 0), (1080, 12)], fill=hex_to_rgb(C_DARK))

    # Headline
    font_headline = load_font("PlayfairDisplay-Bold.ttf", 72)
    y = draw_wrapped_text(draw, slide["headline"].upper(), font_headline,
                          60, 160, 960, hex_to_rgb(C_WHITE), line_spacing=1.2)

    # Body
    font_body = load_font("SourceSerif4-Regular.ttf", 40)
    draw_wrapped_text(draw, slide["body"], font_body,
                      60, y + 60, 960, hex_to_rgb(C_WHITE), line_spacing=1.5)

    # Dark follow box at bottom
    draw.rectangle([(0, 880), (1080, 1080)], fill=hex_to_rgb(C_DARK))
    font_follow = load_font("SourceSerif4-Regular.ttf", 34)
    draw.text((540, 980), "FOLLOW @WORLDGEOPOLITICS FOR UPDATES",
              font=font_follow, fill=hex_to_rgb(C_WHITE), anchor="mm")

    return img

def generate_slides(data):
    print("🎨 Generating slide images...")
    images = []
    for slide in data["slides"]:
        n = slide["slide_number"]
        if n == 1:
            img = make_slide_1(slide)
        elif n == 10:
            img = make_slide_10(slide)
        else:
            img = make_slide_body(slide, n)
        images.append(img)
        print(f"  ✅ Slide {n} generated")
    return images

# ─── CLOUDINARY UPLOAD ───────────────────────────────────────────────────────

def upload_images_to_cloudinary(images, topic):
    print("☁️  Uploading images to Cloudinary...")
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    urls = []
    slug = topic.lower().replace(" ", "_")[:30]
    ts   = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M")

    for i, img in enumerate(images):
        tmp_path = f"/tmp/slide_{i+1:02d}.jpg"
        img.save(tmp_path, "JPEG", quality=92)
        public_id = f"geopolitics/{slug}_{ts}_slide_{i+1:02d}"
        try:
            result = cloudinary.uploader.upload(
                tmp_path,
                public_id=public_id,
                overwrite=True,
                resource_type="image"
            )
            url = result["secure_url"]
            urls.append(url)
            print(f"  ✅ Slide {i+1} uploaded: {url}")
        except Exception as e:
            raise RuntimeError(f"Cloudinary upload failed for slide {i+1}: {e}\nResponse: {result if 'result' in dir() else 'N/A'}")
    return urls

# ─── INSTAGRAM POSTING ───────────────────────────────────────────────────────

def post_carousel_to_instagram(image_urls, caption, hashtags):
    print("📸 Posting carousel to Instagram...")
    full_caption = f"{caption}\n\n{hashtags}"
    container_ids = []

    # Step 1: Upload each image as carousel item
    for i, url in enumerate(image_urls):
        payload = {
            "image_url": url,
            "is_carousel_item": "true",
            "access_token": INSTAGRAM_ACCESS_TOKEN
        }
        r = requests.post(f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media", data=payload)
        resp = r.json()
        if "id" not in resp:
            raise RuntimeError(f"Failed to create container for slide {i+1}: {resp}")
        container_ids.append(resp["id"])
        print(f"  ✅ Container created for slide {i+1}: {resp['id']}")
        time.sleep(1)

    # Step 2: Create carousel container
    carousel_payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(container_ids),
        "caption": full_caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    r = requests.post(f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media", data=carousel_payload)
    carousel_resp = r.json()
    if "id" not in carousel_resp:
        raise RuntimeError(f"Failed to create carousel container: {carousel_resp}")
    creation_id = carousel_resp["id"]
    print(f"  ✅ Carousel container created: {creation_id}")

    # Step 3: Wait for processing
    print("  ⏳ Waiting 10 seconds for Instagram processing...")
    time.sleep(10)

    # Step 4: Publish
    publish_payload = {
        "creation_id": creation_id,
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    r = requests.post(f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media_publish", data=publish_payload)
    pub_resp = r.json()
    if "id" not in pub_resp:
        raise RuntimeError(f"Failed to publish carousel: {pub_resp}")
    post_id = pub_resp["id"]
    print(f"  ✅ Carousel published! Post ID: {post_id}")
    return post_id

# ─── GOOGLE SHEETS LOGGING ───────────────────────────────────────────────────

def log_to_google_sheets(data, post_id):
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
            post_id,
            "✅ Posted"
        ]
        sheet.append_row(row)
        print(f"  ✅ Logged to Google Sheets")
    except Exception as e:
        print(f"  ⚠️  Google Sheets logging failed (non-fatal): {e}")

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🌍 GEOPOLITICS BOT — STARTING RUN")
    print(f"🕐 UTC: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. Research + write content
    data = fetch_content_from_gemini()

    # 2. Generate slide images
    images = generate_slides(data)

    # 3. Upload to Cloudinary
    image_urls = upload_images_to_cloudinary(images, data["topic"])

    # 4. Post to Instagram
    post_id = post_carousel_to_instagram(
        image_urls, data["caption"], data["hashtags"]
    )

    # 5. Log to Google Sheets
    log_to_google_sheets(data, post_id)

    print("=" * 60)
    print(f"🎉 SUCCESS — Post ID: {post_id}")
    print(f"📰 Topic: {data['topic']}")
    print(f"🌏 Region: {data['region']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
