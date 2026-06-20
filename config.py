# -*- coding: utf-8 -*-
"""config.py - 优衣库国际官网图片爬虫配置文件"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")
LOG_DIR = os.path.join(BASE_DIR, "logs")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")

# 目标
TARGET_URL = "https://www.uniqlo.com/us/en/men/shirts-and-polos"
COMMERCE_API = "https://www.uniqlo.com/us/api/commerce/v5/en"

# 商品列表 API (男装衬衫)
LISTING_PATH = "22211,95669,,"
LISTING_PARAMS = {
    "path": LISTING_PATH,
    "offset": 0,
    "limit": 36,
    "imageRatio": "3x4",
}

# 网络
PROXY = "http://127.0.0.1:7892"
USE_PROXY = True

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# 延迟 & 超时
REQUEST_DELAY = 1.5
DOWNLOAD_CONCURRENCY = 8
REQUEST_TIMEOUT = 15

# 重试
MAX_RETRIES = 3
MAX_CONSECUTIVE_FAILURES = 5
RETRY_BASE_DELAY = 1

# 图片
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MIN_IMAGE_SIZE = 1024
MAX_NAME_LENGTH = 40

# UA 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
