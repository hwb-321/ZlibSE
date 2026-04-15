# ZlibSE Backend

ZlibSE Backend 是一个基于 FastAPI 的电子书管理后端，围绕用户认证、书籍检索、收藏、文件上传、对象存储下载、异步解析和缓存优化展开。

项目当前默认按完整能力运行：MySQL 作为业务数据事实源，Redis 作为共享缓存和分布式协调组件，进程内 TTLCache 提供一级缓存，腾讯云 COS 保存文件，RabbitMQ 承担异步解析任务。

## 核心能力

- 用户认证：验证码、注册、登录、JWT 鉴权、`/me`、修改密码。
- 书籍业务：创建书籍、分页列表、计数、详情、搜索。
- 收藏业务：收藏状态、增删收藏、收藏列表。
- 文件业务：draft、上传会话、上传完成、解析状态、下载地址。
- 上传记录：上传列表、删除书籍及关联文件。
- 异步解析：RabbitMQ worker、对象存储读写、解析结果入库、自动封面。
- 缓存体系：TTLCache、Redis、空值缓存、随机 TTL 抖动、Redis 重建锁、布隆过滤器。
- 调试指标：请求、SQL、缓存、锁等指标写入 Redis，可通过 `/debug/metrics` 查看。

## 架构文档

后端文档集中放在 `document/` 下，建议先看整体架构，再看接口和模块细节：

- [后端接口说明](./document/后端接口说明.md)
- [数据库格式说明](./document/数据库格式说明.md)
- [后续优化记录](./document/后续优化记录.md)
- [模块图表索引](./document/模块图表/README.md)
- [整体架构图](./document/模块图表/00-整体架构.md)
- [认证模块图](./document/模块图表/01-认证模块.md)
- [书籍模块图](./document/模块图表/02-书籍模块.md)
- [收藏模块图](./document/模块图表/03-收藏模块.md)
- [文件模块图](./document/模块图表/04-文件模块.md)
- [上传记录模块图](./document/模块图表/05-上传记录模块.md)
- [异步解析模块图](./document/模块图表/06-异步解析模块.md)
- [启动与基础设施图](./document/模块图表/07-启动与基础设施.md)
- [缓存体系总览图](./document/模块图表/08-缓存体系总览.md)

## 技术栈

- Web 框架：FastAPI、Uvicorn
- ORM：SQLAlchemy
- 数据库：MySQL
- 缓存与协调：Redis、cachetools TTLCache
- 对象存储：腾讯云 COS 的 S3 兼容接口，底层使用 boto3
- 异步任务：RabbitMQ、pika
- 鉴权：JWT、PyJWT
- 文件解析：EbookLib、pypdf、PyMuPDF
- 防穿透：bloom-filter2

完整依赖见 [requirements.txt](./requirements.txt)。

## 快速启动

创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

运行时默认读取 `config.secret.yaml`。仓库中的 [config.yaml](./config.yaml) 是公开配置模板，可以复制后填写本地真实配置。也可以通过环境变量指定：

```bash
export APP_CONFIG_FILE=/path/to/config.secret.yaml
```

初始化数据库结构：

```bash
.venv/bin/python -m fastapi_app.init_db
```

启动后端服务：

```bash
.venv/bin/python -m fastapi_app
```

服务默认监听：

```text
http://127.0.0.1:8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/ping
```

## 配置说明

主要配置项模板在 [config.yaml](./config.yaml)：

- `server`：监听地址、端口、worker 数、访问日志。
- `security`：JWT 密钥、算法、token 过期天数、验证码开关。
- `database`：数据库 URL 或本地 SQLite 路径、连接池参数。
- `redis`：Redis 地址、缓存 TTL、锁 TTL、布隆过滤器参数。
- `local_cache`：进程内一级缓存开关、容量、TTL。
- `async_parse`：RabbitMQ 异步解析开关与队列配置。
- `download_cache`：热点下载签名 URL 缓存配置。
- `storage`：COS bucket、region、endpoint、密钥和对象 key 前缀。

注意：仓库中的 `config.yaml` 只作为公开模板；运行服务前需要准备本地真实配置文件 `config.secret.yaml`，并填写数据库、Redis、COS、JWT 等环境配置。

## 运行模型

启动入口是：

- [fastapi_app/main.py](./fastapi_app/main.py)：创建 FastAPI app。
- [fastapi_app/__main__.py](./fastapi_app/__main__.py)：读取配置并启动 Uvicorn；异步解析开启时会拉起 parse worker。
- [fastapi_app/init_db.py](./fastapi_app/init_db.py)：初始化数据库结构并预热书籍布隆过滤器。

启动阶段会执行：

- 初始化应用 middleware 和路由。
- 预热书籍布隆过滤器。
- 预热对象存储 client。
- 开启 metrics middleware。

更多细节见 [启动与基础设施图](./document/模块图表/07-启动与基础设施.md)。

## 缓存与一致性策略

当前缓存策略可以概括为：

- Auth 使用 `auth_token_version`：MySQL 保存权威版本，Redis 缓存认证版本，JWT 携带 `auth_version`。
- 一级缓存只存 profile，不单独承担认证版本事实源。
- 其他业务缓存不使用版本号 key。
- 业务写入 MySQL commit 成功后删除 Redis 和一级缓存。
- 下一次读 miss 后回源 MySQL，并回填 Redis 与一级缓存。
- Redis 内容缓存写入时使用 TTL 随机抖动。
- 读缓存 miss 后回源路径使用 Redis 重建锁、二次检查和等待重试。

完整说明见 [缓存体系总览图](./document/模块图表/08-缓存体系总览.md) 和 [后端接口说明](./document/后端接口说明.md)。

## 异步解析

真实模式下，正文文件上传完成后会投递 RabbitMQ 解析任务，worker 异步处理：

1. 从 MySQL 读取文件记录。
2. 从 COS 下载原文件。
3. 解析标题、作者、语言、页数等信息。
4. 必要时生成自动封面并上传 COS。
5. 写回 `file_parse_results` 和 `stored_files` 状态。

详见 [异步解析模块图](./document/模块图表/06-异步解析模块.md)。

## 调试指标

开启 `debug_metrics.enabled=true` 后，可查看 Redis 聚合指标：

```bash
curl http://127.0.0.1:8000/debug/metrics
```

清空指标：

```bash
curl -X DELETE http://127.0.0.1:8000/debug/metrics
```

指标覆盖请求耗时、SQL、缓存命中、Redis 锁等，接口细节见 [后端接口说明](./document/后端接口说明.md)。

## 验证

当前仓库没有完整测试用例，基础验证可以先运行：

```bash
.venv/bin/python -m compileall fastapi_app
.venv/bin/python - <<'PY'
from fastapi_app.main import app
print(app.title, len(app.routes))
PY
```

如果后续补充 pytest 用例，可直接运行：

```bash
.venv/bin/pytest
```

## 相关项目

压测脚本仓库位于：

```text
/home/hwb/Workspace/ZlibSE-benchmark
```

压测脚本会生成中文压测结果，并估算请求/响应包大小与带宽。后端侧的 metrics 可配合压测结果一起分析。
