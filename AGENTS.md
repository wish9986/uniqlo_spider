# 项目指令 - uniqlo_spider (优衣库国际官网图片爬取)

## 项目概述

优衣库国际官网 US 站点商品图片爬取工具。从商品列表页获取所有商品的默认颜色轮播主图。

## 项目根目录

E:\workpace\uniqlo_spider

## 技术栈

- Python 3.12 + requests + lxml + Pillow
- 虚拟环境：`venv/`（已创建）
- 代理：`http://127.0.0.1:7892`（VPN）

## 目录结构

```
uniqlo_spider/
├── config.py          # 配置文件（所有参数集中管理）
├── crawler.py         # 正式爬虫（主入口）
├── check_source.py    # 数据源探测脚本（v2）
├── requirements.txt   # 依赖清单
├── images/            # 下载图片（自动生成）
├── logs/              # 运行日志（crawler.log + error.log）
├── progress.json      # 断点续传进度（自动生成）
├── docs/              # 项目文档
├── 开发日志/          # 开发日志
├── SKILL.md           # 技能沉淀文档（可复用于类似项目）
├── AGENTS.md          # 本文件
└── venv/              # Python虚拟环境（不要删除）
```

## 运行方式

```bash
cd E:\workpace\uniqlo_spider
venv\Scripts\python crawler.py
```

## 关键配置参数（config.py）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| PROXY | http://127.0.0.1:7892 | VPN代理 |
| REQUEST_DELAY | 1.5 | API请求间隔（秒） |
| DOWNLOAD_CONCURRENCY | 8 | 图片下载并发数 |
| REQUEST_TIMEOUT | 15 | 请求超时（秒） |
| MAX_RETRIES | 3 | 失败重试次数 |
| LISTING_PARAMS.path | 22211,95669,, | 男装衬衫分类 |

## API 参考

- **Commerce API**：`https://www.uniqlo.com/us/api/commerce/v5/en`
- **商品列表**：`/products?path={path}&offset={n}&limit=36&imageRatio=3x4`
- **商品详情**：`/products/{productId}`

## 代码规范

- 类名：PascalCase
- 函数/变量：snake_case
- 常量：UPPER_SNAKE
- 配置文件集中管理，不硬编码

## 注意事项

1. 运行前确保 VPN 已开启（127.0.0.1:7892）
2. 必须在虚拟环境 `venv\Scripts\python` 下运行
3. 图片保存在 `images/` 目录下
4. 如果中断可重新运行，断点续传自动跳过已完成商品
5. SSL 连接偶有不稳定，重试机制已内置
