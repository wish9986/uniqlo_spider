# 优衣库国际官网商品图片爬虫

爬取优衣库（UNIQLO）国际官网男装衬衫分类的商品信息及轮播主图，支持断点续传、并发下载、代理配置。

## 技术栈

- Python + requests
- 并发下载（ThreadPoolExecutor）
- 断点续传（JSON 进度管理）
- 图片完整性验证（PIL）
- 代理/IP 轮换支持

## 功能特点

- ✅ **API 数据采集**：调用优衣库 Commerce API 获取商品数据
- ✅ **轮播图下载**：提取默认颜色的所有轮播主图
- ✅ **断点续传**：中断后重新运行自动跳过已完成商品
- ✅ **并发下载**：多线程同时下载图片，提高效率
- ✅ **日志系统**：控制台 + 文件双日志，支持 DEBUG 级别
- ✅ **图片验证**：自动检测损坏/不完整图片并删除重下
- ✅ **代理支持**：可选 HTTP 代理

## 项目结构

```
uniqlo_spider/
├── crawler.py          # 主程序（API请求 + 下载器 + 进度管理）
├── config.py           # 配置文件（URL、延迟、代理等）
├── check_source.py     # 数据校验工具
├── requirements.txt    # 依赖清单
├── images/             # 下载图片输出目录
├── logs/               # 运行日志
├── docs/               # 项目文档
└── progress.json       # 断点续传进度文件
```

## 使用方法

```bash
# 安装依赖
pip install -r requirements.txt

# 运行爬虫
python crawler.py
```

运行前可根据需要修改 `config.py`：
- `USE_PROXY`：是否启用代理
- `REQUEST_DELAY`：请求间隔（秒）
- `DOWNLOAD_CONCURRENCY`：并发下载线程数

## 反爬策略

- 伪造完整浏览器请求头（User-Agent、Referer、Origin）
- 请求间隔随机化，避免触发频率限制
- 支持代理 IP，分散请求来源
- API 直连，跳过页面解析

## 相关项目

- [bilibili_popular_downloader](https://github.com/wish9986/bilibili_popular_downloader) — B站综合热门视频下载器
- [netease_music_crawler](https://github.com/wish9986/netease_music_crawler) — 网易云音乐热歌榜爬虫
