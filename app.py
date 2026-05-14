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
        time.sleep(3)

        title = page.query_selector("#productTitle")
        title = title.inner_text().strip() if title else "N/A"

        # Wait for price to load
        time.sleep(2)

        # MRP - get all offscreen prices, last one is usually MRP
        mrp = "N/A"
        try:
            mrp_el = page.query_selector("span.a-price.a-text-price span.a-offscreen")
            if mrp_el:
                mrp = mrp_el.inner_text().strip()
            if mrp == "N/A":
                # Try basisPrice
                mrp_el = page.query_selector(".basisPrice span.a-offscreen")
                if mrp_el:
                    mrp = mrp_el.inner_text().strip()
            if mrp == "N/A":
                # Get all offscreen and find strikethrough context
                mrp_els = page.query_selector_all("span.a-offscreen")
                for el in mrp_els:
                    parent = page.evaluate("el => el.closest('.a-text-price') ? el.closest('.a-text-price').getAttribute('data-a-strike') : null", el)
                    if parent == "true":
                        mrp = el.inner_text().strip()
                        break
        except:
            pass

        # Selling Price
        price = "N/A"
        try:
            price_el = page.query_selector("#corePriceDisplay_desktop_feature_div .a-price-whole")
            if not price_el:
                price_el = page.query_selector(".a-price.priceToPay .a-price-whole")
            if not price_el:
                price_el = page.query_selector(".a-price-whole")
            if price_el:
                whole = price_el.inner_text().strip().replace(",","").replace(".","")
                price = f"₹{whole}"
        except:
            pass

        # Sold By
        sold_by = "N/A"
        try:
            sold_selectors = [
                "#sellerProfileTriggerId",
                "#tabular-buybox-truncate-0 .a-link-normal",
                "#merchantInfoFeature_feature_div .a-link-normal",
                "#merchant-info a",
            ]
            for sel in sold_selectors:
                el = page.query_selector(sel)
                if el:
                    txt = el.inner_text().strip()
                    if txt:
                        sold_by = txt
                        break
        except:
            pass

        # Deal Tag
        deal = "N/A"
        try:
            deal_selectors = [
                "#dealBadgeSupportingText",
                "#apex_offerDisplay_desktop .a-badge-text",
                ".dealBadge span",
                "#dealsAccordion .a-badge-text",
            ]
            for sel in deal_selectors:
                el = page.query_selector(sel)
                if el:
                    txt = el.inner_text().strip()
                    if txt:
                        deal = txt
                        break
        except:
            pass

        # Rating
        rating = "N/A"
        try:
            rating_el = page.query_selector("#acrPopover")
            if rating_el:
                title_attr = rating_el.get_attribute("title")
                if title_attr:
                    rating = title_attr.split(" ")[0]
            if rating == "N/A":
                rating_el = page.query_selector("span.a-icon-alt")
                if rating_el:
                    rating = rating_el.inner_text().strip().split(" ")[0]
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
                    args=["--no-sandbox", "--disable-setuid-sandbox",
                          "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
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
