# -*- coding: utf-8 -*-
"""
check_source.py - 优衣库国际官网数据源探测脚本 (v2)
=================================================
探测目标: https://www.uniqlo.com/us/en/men/shirts-and-polos
"""

import requests
import re
import json
import time
import os
import warnings
from urllib.parse import urljoin, urlencode, quote
from datetime import datetime

warnings.filterwarnings("ignore")

TARGET_URL = "https://www.uniqlo.com/us/en/men/shirts-and-polos"
DETAIL_URL = "https://www.uniqlo.com/us/en/products/E477181-000/00?colorDisplayCode=37&sizeDisplayCode=003"
BASE_DOMAIN = "https://www.uniqlo.com"
PROXY = "http://127.0.0.1:7892"
COMMERCE_API = "https://www.uniqlo.com/us/api/commerce/v5/en"

USER_XPATH_PRODUCT = '//a[@target="_self" and contains(@href,"products")]/@href'
USER_XPATH_IMAGE = '//img[@class="image__img"]/@src'
USER_XPATH_TITLE = '//h2[text()]'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
PROXIES = {"http": PROXY, "https": PROXY}
SESSION = requests.Session()
SESSION.proxies = PROXIES
SESSION.headers.update(HEADERS)
SESSION.verify = False


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


def header(msg):
    w = 60
    print(f"\n{'='*w}\n  {msg}\n{'='*w}")


def safe_get(url, timeout=15, **kwargs):
    for attempt in range(3):
        try:
            h = {**HEADERS, **kwargs.pop("headers", {})}
            return SESSION.get(url, timeout=timeout, headers=h, **kwargs)
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                raise e


# ============================================================
# 测试 A: 静态 HTML
# ============================================================
def test_a_static_html():
    header("测试 A: 静态 HTML 检测")
    result = {"status": "unknown", "detail": ""}
    try:
        resp = safe_get(TARGET_URL, timeout=30)
        html = resp.text
        log(f"状态码: {resp.status_code}, 页面大小: {len(html)} 字符")

        product_links = re.findall(r'href="([^"]*products/[A-Z0-9]+[^"]*)"', html)
        product_links = [l for l in product_links if "member/orders" not in l]
        log(f"商品详情页链接数: {len(product_links)}")

        if len(product_links) > 5:
            result["status"] = "success"
            result["detail"] = f"静态 HTML 包含 {len(product_links)} 个商品链接"
        elif len(product_links) > 0:
            result["status"] = "partial"
            result["detail"] = f"静态 HTML 仅 {len(product_links)} 个链接"
        else:
            result["status"] = "failed"
            result["detail"] = "静态 HTML 不含商品链接 (JS 动态加载)"
        result["detail"] += f" | 状态码={resp.status_code}"
    except Exception as e:
        log(f"异常: {e}", "ERROR")
        result["status"] = "error"
        result["detail"] = str(e)
    return result


# ============================================================
# 测试 B: XPath 匹配
# ============================================================
def test_b_xpath_match():
    header("测试 B: XPath 容器检测")
    result = {"status": "unknown", "detail": ""}
    try:
        resp = safe_get(TARGET_URL, timeout=30)
        from lxml import html as lxml_html
        tree = lxml_html.fromstring(resp.text)

        user_links = tree.xpath(USER_XPATH_PRODUCT)
        log(f"用户 XPath (商品链接): {len(user_links)} 个")

        user_imgs = tree.xpath(USER_XPATH_IMAGE)
        log(f"用户 XPath (图片): {len(user_imgs)} 个")

        containers = {}
        for cls in ["product", "item", "card", "tile", "goods", "product-card"]:
            m = tree.xpath(f'//*[contains(@class, "{cls}")]')
            if m:
                containers[cls] = len(m)
        log(f"自动检测容器: {containers}")

        if len(user_links) > 5:
            result["status"] = "success"
            result["detail"] = "XPath 可在静态 HTML 中定位商品链接"
        elif containers:
            result["status"] = "partial"
            result["detail"] = f"发现容器特征: {list(containers.keys())}, 但用户 XPath 匹配不足"
        else:
            result["status"] = "failed"
            result["detail"] = "静态 HTML 中无匹配 (JS 动态渲染)"
    except ImportError:
        result["status"] = "skipped"
        result["detail"] = "lxml 未安装"
    except Exception as e:
        result["status"] = "error"
        result["detail"] = str(e)
    return result


# ============================================================
# 测试 C: Selenium 渲染验证
# ============================================================
def test_c_selenium():
    header("测试 C: Selenium 渲染验证")
    result = {"status": "unknown", "detail": ""}
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_exception({"excludeSwitches": ["enable-logging"]})

        log("启动 Chrome 无头浏览器...")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)

        try:
            log(f"加载: {TARGET_URL}")
            driver.get(TARGET_URL)
            time.sleep(8)

            log(f"页面标题: {driver.title}")
            from selenium.webdriver.common.by import By
            links = driver.find_elements(By.XPATH, "//a[contains(@href, 'products')]")
            prod_links = [l.get_attribute("href") for l in links
                          if l.get_attribute("href") and "/products/" in l.get_attribute("href")
                          and "member/orders" not in l.get_attribute("href")]
            prod_links = list(set(prod_links))
            log(f"商品链接数: {len(prod_links)}")
            for l in prod_links[:5]:
                log(f"  {l}")

            if len(prod_links) > 10:
                result["status"] = "success"
                result["detail"] = f"Selenium 渲染后获取 {len(prod_links)} 个商品链接"
            elif len(prod_links) > 0:
                result["status"] = "partial"
                result["detail"] = f"仅获取 {len(prod_links)} 个链接"
            else:
                result["status"] = "failed"
                result["detail"] = "渲染后未找到商品链接"

        finally:
            driver.quit()
    except Exception as e:
        log(f"Selenium 异常: {e}", "ERROR")
        result["status"] = "error"
        result["detail"] = str(e).split("\n")[0]
    return result


# ============================================================
# 测试 D: API 端点深度探测 (核心改进)
# ============================================================
def test_d_api_detection():
    header("测试 D: API 端点深度探测")
    result = {"status": "unknown", "detail": "", "endpoints": []}

    def report_api(found_url, source, resp_data):
        entry = {"url": found_url, "source": source}
        if resp_data:
            items = resp_data.get("result", {}).get("items", [])
            total = resp_data.get("result", {}).get("pagination", {}).get("total", 0)
            entry["products"] = len(items)
            entry["total"] = total
            if items:
                entry["sample"] = items[0].get("productId", items[0].get("name", "N/A"))
        result["endpoints"].append(entry)
        log(f"  [FOUND] {source}: {found_url}")
        if resp_data:
            log(f"          items={len(items)}, total={total}")

    found_api = False

    # ----- 1. 探测目标页面的静态HTML，提取分类ID -----
    log("步骤1: 从页面HTML提取分类/性别ID...")
    try:
        resp = safe_get(TARGET_URL, timeout=30)
        html = resp.text

        # 提取所有5位数字ID (常见的UNIQLO分类ID格式)
        all_ids = set(re.findall(r'["\'">](\d{4,6})["\'"<]', html))
        log(f"  提取到 {len(all_ids)} 个候选数字ID")

        # 尝试定位 gender 和 category 的 key ID
        gender_ids = set()
        category_ids = set()
        for attr_name in ["data-gender-id", "data-category-id", "data-level-id",
                           "genderId", "categoryId", "classId", "levelId"]:
            for m in re.findall(rf'{attr_name}["\'=\s:]+(\d{{4,6}})["\'\s,]', html, re.IGNORECASE):
                gender_ids.add(m)

        log(f"  关联gender/category的ID: {list(gender_ids)[:10]}")
        if not gender_ids:
            gender_ids = all_ids

        # 从URL路径提取可能的关键词
        path_parts = [p for p in TARGET_URL.split("/") if p][-2:]  # ["men", "shirts-and-polos"]
        log(f"  URL路径片段: {path_parts}")

    except Exception as e:
        log(f"  HTML解析异常: {e}", "WARN")
        gender_ids = set()

    # ----- 2. 深度搜索 JS bundle 中的 API 路径 -----
    log("\n步骤2: 从JS bundle挖掘API构造模式...")
    try:
        resp = safe_get(TARGET_URL, timeout=20)
        scripts = re.findall(r'src="([^"]+\.js[^"]*)"', resp.text)
        main_js = None
        for s in scripts:
            if "main-" in s and s.endswith(".js"):
                main_js = s if s.startswith("http") else urljoin(BASE_DOMAIN, s)
                break

        if main_js:
            log(f"  JS bundle: {main_js.split('/')[-1][:60]}")
            jsr = safe_get(main_js, timeout=20)
            js_text = jsr.text

            # 搜索 /api/commerce 模式
            for pattern in ["commerce", "api/commerce", "commerce/v5"]:
                idx = js_text.find(pattern)
                if idx >= 0:
                    ctx = js_text[max(0, idx - 80):idx + 200]
                    log(f"  发现 '{pattern}' 在JS中 (pos {idx})")
                    # 提取附近的字符串常量
                    urls_in_ctx = re.findall(r'["\'](/[a-zA-Z0-9_/{}[\]-]+(?:products|categories)[a-zA-Z0-9_/{}\[\]-]*)["\']', ctx)
                    if urls_in_ctx:
                        for u in urls_in_ctx:
                            log(f"    提取路径: {u}")

            # 提取所有潜在API路由
            api_routes = set()
            for m in re.findall(r'["\'](/[a-zA-Z0-9_/-]+(?:api|commerce|products|categories|v[0-9]+)[a-zA-Z0-9_/-]{5,})["\']', js_text):
                if not m.startswith("//") and not any(ext in m for ext in [".css", ".js", ".png", ".jpg"]):
                    api_routes.add(m)
            log(f"  提取到 {len(api_routes)} 个潜在API路由")
            for route in sorted(api_routes)[:8]:
                log(f"    {route}")
    except Exception as e:
        log(f"  JS分析异常: {e}", "WARN")

    # ----- 3. 直接探测 commerce API 基础端点 -----
    log("\n步骤3: 探测 Commerce API 基础端点...")

    # 3a. 单商品详情API
    try:
        r = safe_get(f"{COMMERCE_API}/products/E477181-000",
                      timeout=15, headers={"Accept": "application/json"})
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 200 and ("json" in ct or r.text.startswith("{")):
            d = r.json()
            if d.get("status") == "ok" and "result" in d:
                report_api(f"{COMMERCE_API}/products/{{productId}}",
                          "单商品详情API", None)
                found_api = True
                # 展示商品详情API返回的图片
                res = d.get("result", {})
                if "images" in res:
                    main_imgs = res["images"].get("main", {})
                    log(f"  商品详情: 主图颜色数={len(main_imgs)}")
                    for c, img_data in list(main_imgs.items())[:2]:
                        log(f"    颜色{c}: {img_data['image'][:120]}")
    except Exception as e:
        log(f"  单商品API探测失败: {e}", "WARN")

    # 3b. 商品列表API - 用从HTML提取的ID构建path参数
    log("\n步骤4: 构建商品列表 API (带path参数)...")

    # 测试不同的path组合
    path_candidates = []
    if gender_ids:
        # 用最可能的主分类ID
        primary_ids = sorted(gender_ids, key=lambda x: (len(x), x))
        for gid in list(primary_ids)[:5]:
            path_candidates.append(f"{gid},,")  # 只有性别
            path_candidates.append(f"{gid},95669,,")  # 性别+衬衫分类
            path_candidates.append(f"{gid},95668,,")
            path_candidates.append(f"{gid},95672,,")

    # 添加最可能的候选
    path_candidates = list(set(path_candidates))
    path_candidates.insert(0, "22211,95669,,")  # 用户已验证的
    path_candidates.insert(0, "22211,,")  # 全男装

    tested_paths = set()
    for path_val in path_candidates:
        if path_val in tested_paths:
            continue
        tested_paths.add(path_val)

        params = {"path": path_val, "limit": "5", "imageRatio": "3x4"}
        url = f"{COMMERCE_API}/products?{urlencode(params)}"
        try:
            r = safe_get(url, timeout=15, headers={"Accept": "application/json"})
            if r.status_code != 200:
                continue
            ct = r.headers.get("Content-Type", "")
            if "json" not in ct and not r.text.startswith("{"):
                continue
            d = r.json()
            if d.get("status") != "ok":
                continue
            items = d.get("result", {}).get("items", [])
            total = d.get("result", {}).get("pagination", {}).get("total", 0)
            log(f"  path={path_val}: items={len(items)}, total={total}")

            if len(items) > 0 and total > 0:
                sample_product = items[0]
                report_api(
                    f"{COMMERCE_API}/products?path={path_val}&offset={{offset}}&limit={{limit}}&imageRatio=3x4",
                    f"商品列表API (path={path_val})", d
                )
                found_api = True

                # 展示第一个商品的图片信息
                sample_name = sample_product.get("name", "N/A")
                sample_id = sample_product.get("productId", "N/A")
                main_imgs = sample_product.get("images", {}).get("main", {})
                log(f"  示例商品: {sample_id} - {sample_name}")
                log(f"  主图数量: {len(main_imgs)} 张 ({list(main_imgs.keys())[:6]})")

        except Exception as e:
            pass

    # 3c. 尝试其他 commerce API 端点
    log("\n步骤5: 探测其他 Commerce API 端点...")
    other_endpoints = [
        f"{COMMERCE_API}/categories?genderId=22211",
    ]
    for ep in other_endpoints:
        try:
            r = safe_get(ep, timeout=10, headers={"Accept": "application/json"})
            if r.status_code == 200:
                try:
                    d = r.json()
                    if d.get("status") == "ok":
                        log(f"  {ep.split('/')[-1].split('?')[0]}: 可用")
                        result["endpoints"].append({"url": ep, "source": "categories API"})
                except:
                    pass
        except:
            pass

    # ----- 结论 -----
    if found_api:
        result["status"] = "success"
        result["detail"] = f"发现 {len(result['endpoints'])} 个可用 API 端点"
    else:
        result["status"] = "failed"
        result["detail"] = "未发现可用 API 端点"

    return result


# ============================================================
# 测试 E: 反爬检测
# ============================================================
def test_e_anti_crawl():
    header("测试 E: 反爬检测")
    result = {"status": "clean", "detail": "", "checks": {}}
    try:
        resp = safe_get(TARGET_URL, timeout=30)
        headers = resp.headers
        html = resp.text
        sc = resp.status_code

        checks = {"status_code": sc, "server": headers.get("Server", "unknown")}

        if sc in (403, 503, 429):
            log(f"状态码 {sc} - 可能被拦截!")
            result["status"] = "blocked"
        else:
            log(f"状态码 {sc} - 正常")

        # Cloudflare
        cf = any(k in html.lower() or k in str(headers).lower()
                 for k in ["cloudflare", "__cfduid", "cf-ray"])
        checks["cloudflare"] = cf
        log(f"Cloudflare: {'检测到!' if cf else '无'}")

        # Captcha
        cap = any(k in html.lower() for k in ["captcha", "recaptcha", "hcaptcha", "verify you are human"])
        checks["captcha"] = cap
        log(f"验证码: {'检测到!' if cap else '无'}")

        result["checks"] = checks
        if result["status"] == "clean":
            result["detail"] = "反爬检测通过"
    except Exception as e:
        result["status"] = "error"
        result["detail"] = str(e)
    return result


# ============================================================
# 测试 F: 登录态检测
# ============================================================
def test_f_login_required():
    header("测试 F: 登录态检测")
    result = {"status": "no_login", "detail": ""}
    try:
        # 检查详情页是否可访问
        log("检查详情页访问...")
        dr = safe_get(DETAIL_URL, timeout=30)
        log(f"详情页状态码: {dr.status_code}")
        if dr.status_code == 200:
            log("详情页可自由访问")
            result["detail"] = "无需登录"
        else:
            result["status"] = "login_required"
            result["detail"] = f"详情页状态码: {dr.status_code}"

        # 检查API是否需要特殊认证
        log("\n检查API认证需求...")
        api_url = f"{'https://www.uniqlo.com/us/api/commerce/v5/en/products'}?path=22211,95669,,&limit=3&imageRatio=3x4"
        ar = safe_get(api_url, timeout=15, headers={"Accept": "application/json"})
        log(f"API状态码: {ar.status_code}")
        if ar.status_code == 200:
            log("API 无认证需求")
        else:
            log(f"API需要认证: {ar.status_code}")

    except Exception as e:
        log(f"异常: {e}", "ERROR")
        result["status"] = "error"
        result["detail"] = str(e)
    return result


# ============================================================
# 测试 G: robots.txt
# ============================================================
def test_g_robots_txt():
    header("测试 G: robots.txt 合规检测")
    result = {"status": "allowed", "detail": ""}
    try:
        r = safe_get(urljoin(BASE_DOMAIN, "/robots.txt"), timeout=15)
        log(f"获取成功 ({len(r.text)} 字符)")

        if "#US" in r.text:
            us = r.text[r.text.index("#US"):]
            us = us[:us.index("\n\n#")] if "\n\n#" in us else us
            for line in us.split("\n"):
                if line.strip():
                    log(f"  {line.strip()}")

        target = "/us/en/men/"
        disallowed = any(f"Disallow: {target}" in l for l in r.text.split("\n"))
        if disallowed:
            result["status"] = "disallowed"
            result["detail"] = f"robots.txt 禁止 {target}"
        else:
            log(f"目标路径 {target} 未被禁止")
            result["detail"] = "robots.txt 合规"
    except Exception as e:
        result["status"] = "unknown"
        result["detail"] = f"获取失败: {e}"
    return result


# ============================================================
# 详情页分析
# ============================================================
def analyze_detail_page():
    header("附加: 详情页静态分析")
    result = {}
    try:
        resp = safe_get(DETAIL_URL, timeout=30)
        log(f"状态码: {resp.status_code}, 大小: {len(resp.text)} 字符")

        from lxml import html as lxml_html
        tree = lxml_html.fromstring(resp.text)
        imgs = tree.xpath(USER_XPATH_IMAGE)
        log(f"用户XPath图片匹配: {len(imgs)} 个")

        all_u = re.findall(r'https://image\.uniqlo\.com[^"\'\s]*(?:jpg|png|webp)', resp.text)
        log(f"UNIQLO图片URL: {len(all_u)} 个")

        for cat in ["chip", "item", "sub", "feature"]:
            cu = list(set(u for u in all_u if f"/{cat}/" in u))
            log(f"  {cat}/: {len(cu)} 张")

        item_imgs = list(set(u for u in all_u if "/item/" in u))
        result["item_images"] = item_imgs
        result["total_images"] = len(all_u)
    except Exception as e:
        log(f"异常: {e}", "ERROR")
    return result


# ============================================================
# 主函数
# ============================================================
def main():
    print(f"\n{'='*60}")
    print(f"  优衣库国际官网 - 数据源探测脚本 v2")
    print(f"  目标: {TARGET_URL}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = {}
    results["test_a"] = test_a_static_html()
    results["test_b"] = test_b_xpath_match()
    results["test_c"] = test_c_selenium()
    results["test_d"] = test_d_api_detection()
    results["test_e"] = test_e_anti_crawl()
    results["test_f"] = test_f_login_required()
    results["test_g"] = test_g_robots_txt()
    detail_result = analyze_detail_page()

    # 综合结论
    print(f"\n{'='*60}")
    print(f"  [总结] 测试结果")
    print(f"{'='*60}")

    icons = {
        "success": "PASS", "failed": "FAIL", "partial": "WARN",
        "clean": "PASS", "no_login": "PASS", "allowed": "PASS",
        "error": "FAIL", "skipped": "SKIP", "blocked": "FAIL",
    }
    for name, key in [("A-静态HTML", "test_a"), ("B-XPath匹配", "test_b"),
                       ("C-Selenium渲染", "test_c"), ("D-API探测", "test_d"),
                       ("E-反爬检测", "test_e"), ("F-登录需求", "test_f"),
                       ("G-robots.txt", "test_g")]:
        s = results[key]["status"]
        icon = icons.get(s, "?")
        print(f"  [{icon}] {name}: {s}")

    # API发现详情
    api_endpoints = results["test_d"].get("endpoints", [])
    if api_endpoints:
        print(f"\n  [INFO] 发现的 API 端点:")
        for ep in api_endpoints:
            desc = ep.get("source", "")
            url_short = ep.get("url", "")[:80]
            products = ep.get("products", 0)
            total = ep.get("total", 0)
            print(f"    - {desc}")
            print(f"      URL: {url_short}")
            if total:
                print(f"      商品: {products}/页, 共{total}个")

    # 推荐策略
    print(f"\n{'='*60}")
    print(f"  [建议] 推荐爬取策略")
    print(f"{'='*60}")
    d_status = results["test_d"]["status"]

    if d_status == "success":
        print(f"\n  推荐: API 策略")
        print(f"  理由: Commerce API 可用，直接返回商品列表+所有颜色主图")
        print(f"  方式:")
        print(f"    1. GET {COMMERCE_API}/products?path={{path}}&offset={{n}}&limit=36&imageRatio=3x4")
        print(f"    2. 从响应中提取 items[].images.main 获取所有主图URL")
        print(f"    3. 多线程并发下载")
        print(f"\n  优势: 不需要Selenium/详情页解析，API一次返回所有数据")
    else:
        print(f"\n  推荐: Selenium 策略")
        print(f"  理由: API不可用，需通过Selenium渲染获取商品链接")

    # 保存结果
    output = {"results": results, "detail_analysis": detail_result,
              "recommendation": {"strategy": "api" if d_status == "success" else "selenium"}}
    with open(os.path.join(os.path.dirname(__file__), "check_result.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存到 check_result.json\n")


if __name__ == "__main__":
    main()
