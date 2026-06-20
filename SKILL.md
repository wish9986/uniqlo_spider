# 电商网站商品图片爬取 Skill

## 概述

本 Skill 总结了从**优衣库国际官网 (uniqlo.com) 商品图片爬取项目**中沉淀的完整工作流。适用于需要从电商网站（尤其是 JS 动态渲染的现代电商）爬取商品图片的场景。

---

## 一、项目工作流（分阶段执行）

### 第一阶段：需求确认

**目标**：与用户确认项目信息，澄清模糊点，不写任何代码。

**需要确认的关键信息清单**：

| 问题 | 示例（优衣库项目） |
|------|-------------------|
| 目标网站基址 | https://www.uniqlo.com/ |
| 入口页面 URL | https://www.uniqlo.com/us/en/men/shirts-and-polos |
| 商品链接特征 | URL 包含 "/products/" |
| 目标数据 | 商品详情页的所有主图 |
| 页面加载方式 | 滚动刷新 / 静态 / 分页 |
| 是否需要登录 | 否 |
| 商品链接 XPath（用户提供） | //a[@target="_self" and contains(@href,"products")]/@href |
| 图片 XPath（用户提供） | //img[@class="image__img"]/@src |
| 图片清洗规则 | 去掉 URL 中的 width 参数 |
| VPN/代理需求 | VPN 端口 7892 |

**可选高级功能（按需启用）**：
- 代理 IP 轮换
- 图片去重（MD5/SHA256）
- 元数据导出（CSV/JSON）
- 运行模式切换（快速/完整）
- 自定义图片存储结构
- 图片范围（所有颜色 / 仅默认颜色）

---

### 第二阶段：环境搭建与探测

**项目目录结构**：
```
项目文件夹/
├── check_source.py    # 探测脚本（7项测试）
├── config.py          # 配置文件
├── crawler.py         # 正式爬虫
├── requirements.txt   # 依赖清单
├── progress.json      # 断点续传（自动生成）
├── images/            # 下载图片（自动生成）
└── logs/              # 运行日志（自动生成）
```

**虚拟环境**：在项目目录下创建 venv，安装依赖：
```bash
python -m venv venv
venv\Scripts\pip install requests selenium lxml Pillow
```

#### check_source.py 7 项探测测试

| 测试 | 内容 | 分析要点 |
|------|------|----------|
| A - 静态 HTML | requests 请求分类页，检查商品链接 | 状态码、页面大小、商品链接数 |
| B - XPath 匹配 | 用用户 XPath + 自动检测容器 | 检查匹配数量，自动发现容器class |
| C - Selenium 渲染 | 无头浏览器加载，检查渲染后结果 | 确认JS动态加载的商品是否可获取 |
| D - API 端点 | 深度探测 JSON 数据接口 | **核心环节**（详见下文） |
| E - 反爬检测 | Cloudflare/403/503/429 | 确认是否有反爬机制 |
| F - 登录态 | 是否需要 Cookie 登录 | 检查页面和API是否需要认证 |
| G - robots.txt | 合规检测 | 确认目标路径是否被禁止 |

#### API 深度探测方法论

这是整个探测环节的**核心**。不要只测试通用 API 模式，而是：

**步骤1：从页面HTML提取分类ID**
```python
# 扫描页面中所有4-6位数字ID
all_ids = set(re.findall(r'["\'>](\d{4,6})["\'<]', html))
# 同时搜索 data-gender-id, data-category-id 等属性
```

**步骤2：搜索 JS bundle 发现 API 路由**
```python
# 寻找 main.js / vendor.js 中的 API 路径
scripts = re.findall(r"src=\"([^\"]+\.js[^\"]*)\"", html)
# 在 JS 中搜索 "commerce", "api/", "products" 等关键词
# 提取附近的 URL 字符串常量
```

**步骤3：构建并测试不同 path 参数组合**
```python
# 用提取的 ID 构建不同参数组合
path_candidates = [
    f"{gender_id},,",           # 全性别
    f"{gender_id},{category_id},,",  # 指定分类
]
# 逐个测试，检查返回的 items 和 total
```

**步骤4：单商品详情 API**
```python
# 测试 /api/commerce/v5/en/products/{productId}
# 验证返回的 images.main / images.sub 结构
```

---

### 第三阶段：正式爬虫

#### 爬虫架构

爬虫采用**3阶段编排** + **生产者-消费者**模式：

```
阶段1: Listing API (自动翻页)
    ↓ productId + representativeColorDisplayCode
阶段2: Detail API (逐个，间隔延迟)
    ↓ 提取 images.main[默认颜色] + images.sub[colorCode=默认颜色]
阶段3: 并发下载 (多线程)
    ↓
images/ 目录
```

#### 核心类结构

| 类 | 职责 |
|----|------|
| `ProgressManager` | progress.json 读写、断点续传跟踪 |
| `APIClient` | API 请求封装、重试、指数退避、UA轮换 |
| `ImageDownloader` | 图片URL提取、多线程下载、校验、MD5去重 |
| `Crawler` | 主流程编排、连续失败检测、中断处理 |

#### 配置项 (config.py)

所有配置集中管理，便于调整：

```python
# 网络
PROXY = "http://127.0.0.1:7892"
REQUEST_DELAY = 1.5      # API 请求间隔
REQUEST_TIMEOUT = 15     # 单次请求超时

# 并发
DOWNLOAD_CONCURRENCY = 8 # 图片下载线程数

# 重试
MAX_RETRIES = 3
MAX_CONSECUTIVE_FAILURES = 5
RETRY_BASE_DELAY = 1
```

#### 默认集成的基础功能

1. **断点续传**：progress.json 记录 completed/downed_images/downloaded，图片未下全不影响商品标记完成
2. **自动翻页**：API offset+limit 翻页
3. **失败重试**：3次 + 指数退避，连续5次失败终止
4. **实时进度保存**：每完成一个商品或图片后更新 progress.json
5. **请求延迟**：默认 1.5 秒，可配置
6. **图片 URL 清洗**：按清洗规则执行（如去掉 width 参数）
7. **图片命名**：`{名称缩写}_{商品编码}_{序号}.jpg`
8. **并发下载**：默认 8 线程
9. **日志系统**：控制台 + 文件日志 + 独立错误日志
10. **UA 轮换**：内置 UA 池，每次请求随机切换
11. **图片校验**：文件大小 + Pillow 验证，删除损坏图片
12. **MD5 去重**：可选

---

## 二、优衣库项目关键发现（案例参考）

### 网站技术栈
- **框架**：服务端渲染 + React 客户端水合（类似 Next.js）
- **渲染方式**：列表页 JS 动态加载，详情页静态 HTML 可用
- **图片 CDN**：`https://image.uniqlo.com/UQ/ST3/` + 路径模板

### Commerce API 结构

**基础路径**：`https://www.uniqlo.com/us/api/commerce/v5/en/`

| 端点 | 说明 | 参数 |
|------|------|------|
| `/products?path={path}` | 商品列表 | path=性别ID,分类ID,, ; offset; limit |
| `/products/{productId}` | 商品详情 | productId (如 E477181-000) |

**path 参数规律**：逗号分隔的分类层级ID
- `22211,95669,,` = 男装(22211), 衬衫(95669)
- `22211,,` = 全男装（527个商品）
- 性别ID `22211` 在页面 HTML 中出现 798 次

### 图片数据结构

```json
{
  "images": {
    "main": {
      "37": {"image": "https://.../item/usgoods_37_477181_3x4.jpg"},
      "64": {"image": "https://.../item/usgoods_64_477181_3x4.jpg"}
    },
    "sub": [
      {"image": "https://.../sub/usgoods_477181_sub3_3x4.jpg", "colorCode": "64"}
    ],
    "chip": {"37": "https://.../chip/goods_37_477181_chip.jpg"}
  }
}
```

- `images.main`：按颜色代码索引的主图（key=displayCode）
- `images.sub`：附加轮播图（每个item有 `colorCode` 字段关联颜色）
- `representativeColorDisplayCode`：默认展示颜色代码

### 图片 URL 模式

```
主图: .../item/{region}goods_{colorCode}_{productId}_3x4.jpg
副图: .../sub/{region}goods_{productId}_sub{N}_3x4.jpg
缩略图: .../chip/goods_{colorCode}_{productId}_chip.jpg
```

### 已知风险
- VPN/代理 SSL 连接不稳定，需要做好重试机制
- 分类 ID 因站点地区（us/en vs jp/ja）不同而变化
- 请求过于频繁可能触发频率限制（429）

---

## 三、技能复用指南

### 适用场景
- 目标网站是电商平台（Shopify / Magento / 自定义）
- 需要爬取商品列表 + 详情页图片
- 网站使用 JS 动态加载（SPA / CSR / SSR）

### 适配新网站需要修改的部分

| 文件 | 修改内容 |
|------|----------|
| `config.py` | API 地址、参数、代理、延迟 |
| `crawler.py` | `APIClient` 中的 API 调用逻辑、`ImageDownloader.extract_images()` 中的图片提取逻辑 |
| `check_source.py` | API 探测的端点列表、XPath 规则 |

### 快速适配检查清单

1. [ ] 确认目标网站的商品列表加载方式
2. [ ] 确认详情页是静态还是动态渲染
3. [ ] 寻找 JSON API（浏览器 DevTools → Network → XHR/Fetch）
4. [ ] 分析商品详情页的图片结构
5. [ ] 确认是否有反爬机制（Cloudflare、验证码、频率限制）
6. [ ] 确认是否需要登录或 Cookie
7. [ ] 确认 robots.txt 是否允许爬取
