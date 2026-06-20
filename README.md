# 优衣库国际官网商品图片爬虫

## 项目简介
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
\\\
uniqlo_spider/
├── crawler.py          # 主程序（API请求 + 下载器 + 进度管理）
├── config.py           # 配置文件（URL、延迟、代理等）
├── images/             # 下载图片输出目录
├── logs/               # 运行日志
└── progress.json       # 断点续传进度文件
\\\

## 使用方法
\\\ash
python crawler.py
\\\

运行前可根据需要修改 config.py：
- \USE_PROXY\: 是否启用代理
- \REQUEST_DELAY\: 请求间隔（秒）
- \DOWNLOAD_CONCURRENCY\: 并发下载线程数

## 数据量
商品数：XXX+ | 图片数：XXX+ 张
