from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import time
import json

app = Flask(__name__)
CORS(app, origins="*")


def scrape_amazon(page, asin):
    try:
        url = f"https://www.amazon.in/dp/{asin}?th=1"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for page to fully render
        time.sleep(4)
        
        # Scroll to trigger lazy loading
        page.mouse.wheel(0, 300)
        time.sleep(1)
        page.mouse.wheel(0, -300)
        time.sleep(1)

        # Check if CAPTCHA
        page_content = page.content()
        if "captcha" in page_content.lower() or "robot" in page_content.lower():
            return {"asin": asin, "status": "error", "error": "CAPTCHA detected"}

        title = page.query_selector("#productTitle")
        title = title.inner_text().strip() if title else "N/A"

        # MRP - multiple strategies
        mrp = "N/A"
        # Strategy 1: basis price (most reliable)
        mrp_el = page.query_selector(".basisPrice .a-offscreen")
        if mrp_el:
            mrp = mrp_el.inner_text().strip()
        # Strategy 2: a-text-price with strike
        if mrp == "N/A":
            mrp_el = page.query_selector(".a-price.a-text-price .a-offscreen")
            if mrp_el:
                mrp = mrp_el.inner_text().strip()
        # Strategy 3: JavaScript evaluation
        if mrp == "N/A":
            try:
                mrp = page.evaluate("""() => {
                    const els = document.querySelectorAll('.a-price.a-text-price span.a-offscreen');
                    for(const el of els) { if(el.textContent.trim()) return el.textContent.trim(); }
                    const basis = document.querySelector('.basisPrice span.a-offscreen');
                    if(basis) return basis.textContent.trim();
                    return 'N/A';
                }""")
            except:
                pass

        # Selling Price
        price = "N/A"
        try:
            price = page.evaluate("""() => {
                const whole = document.querySelector('.a-price.priceToPay .a-price-whole') ||
                              document.querySelector('#corePriceDisplay_desktop_feature_div .a-price-whole') ||
                              document.querySelector('.a-price-whole');
                if(whole) {
                    const txt = whole.textContent.replace(/[,\\.]/g,'').trim();
                    return '₹' + txt;
                }
                return 'N/A';
            }""")
        except:
            pass

        # Sold By
        sold_by = "N/A"
        try:
            sold_by = page.evaluate("""() => {
                const s = document.querySelector('#sellerProfileTriggerId') ||
                          document.querySelector('#tabular-buybox-truncate-0 .a-link-normal') ||
                          document.querySelector('#merchantInfoFeature_feature_div .a-link-normal') ||
                          document.querySelector('#merchant-info a');
                return s ? s.textContent.trim() : 'N/A';
            }""")
        except:
            pass

        # Deal Tag
        deal = "N/A"
        try:
            deal = page.evaluate("""() => {
                const d = document.querySelector('#dealBadgeSupportingText') ||
                          document.querySelector('.dealBadge span') ||
                          document.querySelector('#apex_offerDisplay_desktop .a-badge-text');
                return d ? d.textContent.trim() : 'N/A';
            }""")
        except:
            pass

        # Rating
        rating = "N/A"
        try:
            rating = page.evaluate("""() => {
                const el = document.querySelector('#acrPopover');
                if(el) {
                    const t = el.getAttribute('title');
                    if(t) return t.split(' ')[0];
                }
                const alt = document.querySelector('span.a-icon-alt');
                if(alt) return alt.textContent.split(' ')[0];
                return 'N/A';
            }""")
        except:
            pass

        # Rating Count
        rating_count = "N/A"
        try:
            count_el = page.query_selector("#acrCustomerReviewText")
            if count_el:
                rating_count = count_el.inner_text().strip()
        except:
            pass

        return {
            "asin": asin, "title": title, "mrp": mrp,
            "selling_price": price, "sold_by": sold_by,
            "deal_tag": deal, "rating": rating,
            "rating_count": rating_count, "status": "success"
        }
    except Exception as e:
        return {"asin": asin, "status": "error", "error": str(e)}


def scrape_flipkart(page, fsn):
    try:
        url = f"https://www.flipkart.com/product/p/itme?pid={fsn}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        page.mouse.wheel(0, 300)
        time.sleep(2)

        title = page.query_selector("h1.yhB1nd, h1._9E25nV, .B_NuCI, h1")
        title = title.inner_text().strip() if title else "N/A"

        mrp = "N/A"
        strike_els = page.query_selector_all("[style*='line-through']")
        if strike_els:
            mrp = strike_els[-1].inner_text().strip()

        price_el = page.query_selector("div._30jeq3, ._16Jk6d, .Nx9_7j")
        selling_price = price_el.inner_text().strip() if price_el else "N/A"

        fulfilled_by = "N/A"
        seller_el = page.query_selector("#sellerName, .zN9KaL span, ._2LKZX0")
        if seller_el:
            fulfilled_by = seller_el.inner_text().strip()
        else:
            all_divs = page.query_selector_all("div")
            for d in all_divs:
                try:
                    txt = d.inner_text()
                    if "Fulfilled by" in txt and len(txt) < 80:
                        fulfilled_by = txt.replace("Fulfilled by", "").strip()
                        break
                except:
                    pass

        rating_el = page.query_selector("div._3LWZlK, ._2d4LTz")
        rating = rating_el.inner_text().strip() if rating_el else "N/A"

        count_el = page.query_selector("span._2_R_DZ, span._13vcmD")
        rating_count = count_el.inner_text().strip() if count_el else "N/A"

        return {
            "fsn": fsn, "title": title, "mrp": mrp,
            "selling_price": selling_price, "fulfilled_by": fulfilled_by,
            "rating": rating, "rating_count": rating_count, "status": "success"
        }
    except Exception as e:
        return {"fsn": fsn, "status": "error", "error": str(e)}


def scrape_myntra(page, style_id):
    try:
        url = f"https://www.myntra.com/{style_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        title = page.query_selector("h1.pdp-name, .pdp-name")
        title = title.inner_text().strip() if title else "N/A"

        mrp = page.query_selector(".pdp-price strong, span.pdp-mrp strong")
        mrp = mrp.inner_text().strip() if mrp else "N/A"

        seller = page.query_selector(".SelectedSizeSellerInfo-sellerButton, .pdp-seller-name span")
        seller = seller.inner_text().strip() if seller else "N/A"

        return {
            "style_id": style_id, "title": title,
            "mrp": mrp, "seller": seller, "status": "success"
        }
    except Exception as e:
        return {"style_id": style_id, "status": "error", "error": str(e)}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "World_Scraper Backend Running"})


@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.json
    platform = data.get("platform")
    ids = data.get("ids", [])

    if not platform or not ids:
        return jsonify({"error": "platform and ids required"}), 400

    def generate():
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--flag-switches-begin",
                        "--disable-site-isolation-trials",
                        "--flag-switches-end"
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={
                        "Accept-Language": "en-IN,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    }
                )

                # Stealth: hide webdriver flag
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
                    window.chrome = { runtime: {} };
                """)

                page = context.new_page()

                for i, pid in enumerate(ids):
                    yield f"data: {json.dumps({'type': 'progress', 'current': i+1, 'total': len(ids), 'id': pid})}\n\n"

                    if platform == "amazon":
                        result = scrape_amazon(page, pid)
                    elif platform == "flipkart":
                        result = scrape_flipkart(page, pid)
                    elif platform == "myntra":
                        result = scrape_myntra(page, pid)
                    else:
                        result = {"status": "error", "error": "Unknown platform"}

                    yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"

                browser.close()
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
