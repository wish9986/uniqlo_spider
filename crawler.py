# -*- coding: utf-8 -*-
"""
crawler.py - 优衣库国际官网商品图片爬虫
======================================
策略: API 获取商品数据 → 提取默认颜色的轮播主图 → 并发下载
"""

import os
import sys
import json
import time
import hashlib
import random
import logging
import re
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse, urlencode

import requests
from PIL import Image

import config


# ============================================================
# 工具函数
# ============================================================

def setup_logging():
    """配置日志系统：控制台 + 文件"""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_file = os.path.join(config.LOG_DIR, "crawler.log")
    error_file = os.path.join(config.LOG_DIR, "error.log")

    logger = logging.getLogger("uniqlo_crawler")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    eh = logging.FileHandler(error_file, encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(eh)

    return logger


def clean_image_url(url):
    """清洗图片URL: 去掉 width 参数"""
    parsed = urlparse(url)
    qs = {}
    if parsed.query:
        for pair in parsed.query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k == "width":
                    continue
                qs[k] = v
    new_qs = "&".join(f"{k}={v}" for k, v in qs.items())
    return parsed._replace(query=new_qs).geturl()


def name_abbreviation(full_name):
    """从完整商品名生成缩写（文件名前缀）"""
    name = full_name.split("|")[0].strip()
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > config.MAX_NAME_LENGTH:
        name = name[:config.MAX_NAME_LENGTH].rstrip()
    return name.replace(" ", "_")


def build_filename(product_id, name_abbr, seq, ext=".jpg"):
    """构建文件名: {名称缩写}_{商品编码}_{序号}.jpg"""
    safe_id = re.sub(r"[^\w\-]", "_", product_id)
    return f"{name_abbr}_{safe_id}_{seq:02d}{ext}"


def validate_image(filepath):
    """验证图片完整性: 文件大小 + 文件头"""
    if not os.path.exists(filepath):
        return False
    if os.path.getsize(filepath) < config.MIN_IMAGE_SIZE:
        try:
            os.remove(filepath)
        except OSError:
            pass
        return False
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except Exception:
        try:
            os.remove(filepath)
        except OSError:
            pass
        return False


def file_md5(filepath):
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
# 进度管理器
# ============================================================

class ProgressManager:
    """管理断点续传进度"""

    def __init__(self, logger):
        self.logger = logger
        self.data = self._load()

    def _load(self):
        if os.path.exists(config.PROGRESS_FILE):
            try:
                with open(config.PROGRESS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"进度文件损坏，重新开始: {e}")
        return {
            "products": {},
            "downloaded_images": [],
            "summary": {"total": 0, "completed": 0, "failed": 0},
            "last_update": datetime.now().isoformat(),
        }

    def save(self):
        self.data["last_update"] = datetime.now().isoformat()
        tmp_file = config.PROGRESS_FILE + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, config.PROGRESS_FILE)
        except IOError as e:
            self.logger.error(f"保存进度失败: {e}")

    def is_product_completed(self, product_id):
        entry = self.data["products"].get(product_id)
        return entry and entry.get("status") == "completed"

    def is_image_downloaded(self, filename):
        return filename in self.data["downloaded_images"]

    def mark_product_start(self, product_id, name, total_images):
        self.data["products"][product_id] = {
            "name": name,
            "status": "downloading",
            "total_images": total_images,
            "downloaded": 0,
            "image_files": [],
            "start_time": datetime.now().isoformat(),
        }
        self.save()

    def mark_image_downloaded(self, product_id, filename):
        if filename not in self.data["downloaded_images"]:
            self.data["downloaded_images"].append(filename)
        entry = self.data["products"].get(product_id)
        if entry:
            if filename not in entry["image_files"]:
                entry["image_files"].append(filename)
            entry["downloaded"] = len(entry["image_files"])
        self.save()

    def mark_product_completed(self, product_id):
        entry = self.data["products"].get(product_id)
        if entry:
            entry["status"] = "completed"
            entry["end_time"] = datetime.now().isoformat()
            self.data["summary"]["completed"] += 1
        self.save()

    def mark_product_failed(self, product_id, error):
        entry = self.data["products"].get(product_id)
        if entry:
            entry["status"] = "failed"
            entry["error"] = str(error)
            self.data["summary"]["failed"] += 1
        elif product_id:
            self.data["products"][product_id] = {
                "name": "unknown",
                "status": "failed",
                "error": str(error),
            }
            self.data["summary"]["failed"] += 1
        self.save()

    def get_summary(self):
        return self.data["summary"]


# ============================================================
# API 客户端
# ============================================================

class APIClient:
    """优衣库 Commerce API 客户端"""

    def __init__(self, logger):
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(config.REQUEST_HEADERS)
        self.session.verify = False
        if config.USE_PROXY:
            self.session.proxies = {"http": config.PROXY, "https": config.PROXY}

    def _get_headers(self):
        ua = random.choice(config.USER_AGENTS)
        return {**config.REQUEST_HEADERS, "User-Agent": ua}

    def _request(self, url, desc="", timeout=None):
        last_error = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    headers={**self._get_headers(), "Accept": "application/json"},
                    timeout=timeout or config.REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    wait = 10 * attempt
                    self.logger.warning(f"频率限制({desc})，等待{wait}秒...")
                    time.sleep(wait)
                    continue
                elif resp.status_code >= 500:
                    wait = config.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    self.logger.warning(f"服务器错误 {resp.status_code}({desc})")
                    time.sleep(wait)
                    continue
                else:
                    self.logger.error(f"请求失败 {resp.status_code}({desc}): {resp.text[:200]}")
                    return None
            except requests.exceptions.Timeout:
                wait = config.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                self.logger.warning(f"超时({desc})，重试 {attempt}/{config.MAX_RETRIES}")
                last_error = "timeout"
                time.sleep(wait)
            except requests.exceptions.ConnectionError as e:
                self.logger.warning(f"连接错误({desc}): {e}")
                last_error = str(e)
                time.sleep(config.RETRY_BASE_DELAY * attempt)
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"请求异常({desc}): {e}")
                last_error = str(e)
                time.sleep(config.RETRY_BASE_DELAY)

        self.logger.error(f"重试耗尽({desc})")
        return None

    def fetch_product_list(self):
        """获取商品列表（自动翻页）"""
        all_products = []
        offset = 0
        limit = config.LISTING_PARAMS["limit"]
        total = None
        page = 1

        self.logger.info("=" * 50)
        self.logger.info("开始获取商品列表...")
        self.logger.info("=" * 50)

        while True:
            params = dict(config.LISTING_PARAMS)
            params["offset"] = offset
            params["limit"] = limit
            url = f"{config.COMMERCE_API}/products?{urlencode(params)}"

            self.logger.info(f"  翻页 {page}: offset={offset}")
            data = self._request(url, desc=f"商品列表 page={page}")

            if not data or data.get("status") != "ok":
                self.logger.error(f"获取商品列表失败 (page={page})")
                break

            result = data.get("result", {})
            items = result.get("items", [])
            pagination = result.get("pagination", {})
            total = pagination.get("total", 0)

            if not items:
                self.logger.info("  无更多商品")
                break

            all_products.extend(items)
            self.logger.info(f"  本页 {len(items)} 个，累计 {len(all_products)}/{total}")

            offset += limit
            if offset >= total:
                break

            page += 1
            time.sleep(config.REQUEST_DELAY)

        self.logger.info(f"\n总计 {len(all_products)} 个商品")
        return all_products

    def fetch_product_detail(self, product_id):
        """获取单个商品详情"""
        url = f"{config.COMMERCE_API}/products/{product_id}"
        data = self._request(url, desc=f"详情 {product_id}")
        if data and data.get("status") == "ok":
            return data.get("result")
        return None


# ============================================================
# 图片下载器
# ============================================================

class ImageDownloader:
    """并发图片下载器"""

    def __init__(self, logger, progress):
        self.logger = logger
        self.progress = progress
        self.session = requests.Session()
        self.session.verify = False
        if config.USE_PROXY:
            self.session.proxies = {"http": config.PROXY, "https": config.PROXY}
        os.makedirs(config.IMAGE_DIR, exist_ok=True)

    def extract_images(self, product_detail, default_color):
        """提取默认颜色的所有轮播图URL"""
        images_data = product_detail.get("images", {})
        main_images = images_data.get("main", {})
        sub_images = images_data.get("sub", [])

        urls = []

        default_main = main_images.get(default_color)
        if default_main:
            img_url = default_main.get("image", "")
            if img_url:
                urls.append(clean_image_url(img_url))

        for sub in sub_images:
            if sub.get("colorCode") == default_color:
                img_url = sub.get("image", "")
                if img_url:
                    urls.append(clean_image_url(img_url))

        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def download_single_image(self, url, filepath):
        """下载单张图片，返回 (成功, 消息)"""
        if os.path.exists(filepath):
            if validate_image(filepath):
                return True, "已存在"
            else:
                self.logger.debug(f"  文件损坏，重新下载: {os.path.basename(filepath)}")

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                ua = random.choice(config.USER_AGENTS)
                resp = self.session.get(
                    url,
                    headers={"User-Agent": ua},
                    timeout=config.REQUEST_TIMEOUT,
                )
                if resp.status_code != 200:
                    if attempt < config.MAX_RETRIES:
                        time.sleep(config.RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                        continue
                    return False, f"HTTP {resp.status_code}"

                ct = resp.headers.get("Content-Type", "")
                if "image" not in ct:
                    return False, f"非图片: {ct}"

                with open(filepath, "wb") as f:
                    f.write(resp.content)

                if validate_image(filepath):
                    return True, "成功"
                else:
                    return False, "校验失败"

            except Exception as e:
                if attempt < config.MAX_RETRIES:
                    time.sleep(config.RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                else:
                    return False, str(e)

        return False, "重试耗尽"

    def download_product_images(self, product_id, name, image_urls):
        """下载一个商品的所有图片（多线程）"""
        if not image_urls:
            self.logger.info(f"  无需下载")
            return True, []

        name_abbr = name_abbreviation(name)
        downloaded_files = []
        failed = False

        self.logger.info(f"  下载 {len(image_urls)} 张图片...")

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.DOWNLOAD_CONCURRENCY
        ) as executor:
            future_to_info = {}
            for seq, url in enumerate(image_urls, 1):
                ext = os.path.splitext(urlparse(url).path)[1] or ".jpg"
                if ext.lower() not in config.IMAGE_EXTENSIONS:
                    ext = ".jpg"
                filename = build_filename(product_id, name_abbr, seq, ext)
                filepath = os.path.join(config.IMAGE_DIR, filename)

                if self.progress.is_image_downloaded(filename):
                    self.logger.info(f"  [已下载] {filename}")
                    downloaded_files.append(filename)
                    continue

                future = executor.submit(self.download_single_image, url, filepath)
                future_to_info[future] = (url, filename, filepath, seq)

            for future in concurrent.futures.as_completed(future_to_info):
                url, filename, filepath, seq = future_to_info[future]
                success, msg = future.result()
                if success:
                    downloaded_files.append(filename)
                    self.progress.mark_image_downloaded(product_id, filename)
                    self.logger.info(f"  [{seq}/{len(image_urls)}] {filename} - {msg}")
                else:
                    failed = True
                    self.logger.error(f"  [{seq}/{len(image_urls)}] {filename} - 失败: {msg}")

        all_ok = not failed and len(downloaded_files) == len(image_urls)
        self.logger.info(f"  结果: {len(downloaded_files)}/{len(image_urls)} 张成功")
        return all_ok, downloaded_files


# ============================================================
# 主爬虫
# ============================================================

class Crawler:
    """爬虫主编排器"""

    def __init__(self):
        self.logger = setup_logging()
        self.progress = ProgressManager(self.logger)
        self.api = APIClient(self.logger)
        self.downloader = ImageDownloader(self.logger, self.progress)
        self.consecutive_failures = 0
        self.stop_requested = False

    def run(self):
        self.logger.info("")
        self.logger.info("=" * 55)
        self.logger.info("  优衣库国际官网 - 商品图片爬虫")
        self.logger.info(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"  目标分类: {config.LISTING_PATH}")
        self.logger.info("=" * 55)

        summary = self.progress.get_summary()
        self.logger.info(f"断点续传: 已完成 {summary['completed']} 个，失败 {summary['failed']} 个")

        # ---- 阶段1: 获取商品列表 ----
        self.logger.info("")
        self.logger.info("[阶段1/3] 获取商品列表...")
        products = self.api.fetch_product_list()
        if not products:
            self.logger.error("商品列表为空，终止")
            return

        self.progress.data["summary"]["total"] = len(products)
        self.progress.save()

        # ---- 阶段2: 逐个处理 ----
        self.logger.info("")
        self.logger.info("[阶段2/3] 获取详情并下载图片...")

        pending = [p for p in products
                   if not self.progress.is_product_completed(p.get("productId", ""))]
        skipped = len(products) - len(pending)

        if skipped:
            self.logger.info(f"跳过 {skipped} 个已完成商品，待处理 {len(pending)} 个")

        for idx, product in enumerate(pending, 1):
            if self.stop_requested:
                self.logger.warning("收到终止请求")
                break

            product_id = product.get("productId", "")
            product_name = product.get("name", "未知")
            default_color = str(product.get("representativeColorDisplayCode", ""))

            self.logger.info(f"\n[{idx}/{len(pending)}] {product_id} - {product_name}")
            self.logger.info(f"  默认颜色: {default_color}")

            if not product_id or not default_color:
                self.logger.warning("  缺少必要字段，跳过")
                self.progress.mark_product_failed(product_id or f"unknown_{idx}", "缺字段")
                self.consecutive_failures += 1
                if self.consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
                    self.logger.error(f"连续 {config.MAX_CONSECUTIVE_FAILURES} 次失败，终止")
                    break
                continue

            time.sleep(config.REQUEST_DELAY)
            detail = self.api.fetch_product_detail(product_id)
            if not detail:
                self.logger.warning("  获取详情失败，跳过")
                self.progress.mark_product_failed(product_id, "详情获取失败")
                self.consecutive_failures += 1
                if self.consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
                    self.logger.error(f"连续 {config.MAX_CONSECUTIVE_FAILURES} 次失败，终止")
                    break
                continue

            self.consecutive_failures = 0
            image_urls = self.downloader.extract_images(detail, default_color)
            self.logger.info(f"  轮播图: {len(image_urls)} 张")

            if not image_urls:
                self.logger.warning("  未找到图片")
                self.progress.mark_product_completed(product_id)
                continue

            self.progress.mark_product_start(product_id, product_name, len(image_urls))

            all_ok, downloaded = self.downloader.download_product_images(
                product_id, product_name, image_urls
            )

            if all_ok:
                self.progress.mark_product_completed(product_id)
                self.logger.info(f"  [完成] {product_id}")
            else:
                self.progress.mark_product_failed(product_id, "部分下载失败")
                self.logger.warning(f"  [部分失败] {product_id}")

        # ---- 阶段3: 汇总 ----
        self.logger.info("")
        self.logger.info("[阶段3/3] 汇总结果...")

        final = self.progress.get_summary()
        image_count = len([
            f for f in os.listdir(config.IMAGE_DIR)
            if os.path.isfile(os.path.join(config.IMAGE_DIR, f))
        ]) if os.path.exists(config.IMAGE_DIR) else 0

        self.logger.info("")
        self.logger.info("=" * 55)
        self.logger.info("  爬取完成")
        self.logger.info(f"  总商品: {final.get('total', 0)}")
        self.logger.info(f"  成功: {final.get('completed', 0)}")
        self.logger.info(f"  失败: {final.get('failed', 0)}")
        self.logger.info(f"  图片数: {image_count}")
        self.logger.info(f"  图片目录: {config.IMAGE_DIR}")
        self.logger.info("=" * 55)


if __name__ == "__main__":
    c = Crawler()
    try:
        c.run()
    except KeyboardInterrupt:
        c.logger.warning("用户中断")
        c.stop_requested = True
    except Exception as e:
        c.logger.error(f"异常终止: {e}", exc_info=True)
