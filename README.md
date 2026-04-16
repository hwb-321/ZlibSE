# Benchmark 工具说明

这个仓库用于管理 ZlibSE 后端的压测配置、测试数据生成、测试数据初始化、Locust 压测脚本，以及一个可视化 Gradio 控制台。

## 目录说明

`config.yaml`

- 压测总配置文件。
- 定义后端地址、账号生成参数、Locust 并发参数、执行模式、mock 模式、接口开关，以及各接口自己的分页或搜索参数。

`benchmark_data.yaml`

- 由 `generate_benchmark_data.py` 生成的初始化源数据。
- 每个用户条目同时包含账号信息和该用户要初始化的书籍列表。

`config_loader.py`

- 统一读取和保存 `config.yaml`、`benchmark_data.yaml`。
- 也提供给 Gradio 控制台读取和保存整份 YAML 文本。

`generate_benchmark_data.py`

- 根据 `config.yaml` 中的账号数量、每用户书籍数等参数生成 `benchmark_data.yaml`。

`init_benchmark_data.py`

- 通过 HTTP 调用后端接口初始化压测账号和书籍数据。
- 当前走的是后端新接口链路：
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `POST /api/files/draft`
  - `POST /api/files/{file_id}/upload-session`
  - `POST /api/files/{file_id}/complete`
  - `GET /api/files/{file_id}/parse`
  - `POST /api/books`

`locustfile.py`

- Locust 压测入口。
- 会读取 `config.yaml` 和 `benchmark_data.yaml`，按配置执行并发混跑或串行链路压测。
- 每次测试结束后，会在 `logs/` 下生成中文 Markdown 报告。
- 报告里的 QPS 会同时给出两种口径：
  - `Locust QPS`：Locust 原生统计口径
  - `Duration QPS`：按配置压测时长折算的直观口径，即 `总请求数 / duration`

`gradio_app.py`

- Gradio 控制台。
- 通过表单控件配置压测参数，不需要手改 `config.yaml`。
- 保存时会自动生成新的 `config.yaml`，并触发：
  - 生成 benchmark 数据
  - 初始化 benchmark 数据
  - 启动或停止 Locust
  - 查看 Locust 输出

## 配置说明

### 基础配置

`base_url`

- 被测后端地址。

`accounts`

- `user_count`：生成多少个普通测试用户。
- `username_prefix`：测试用户名统一前缀。
- `email_domain`：测试邮箱域名。
- `default_password`：测试用户默认密码。

`scenarios`

- `vus`：并发虚拟用户数。
- `duration`：压测持续时间。
- `spawn_rate`：每秒启动多少个新用户。
- `wait_time_min_ms` / `wait_time_max_ms`：两次请求之间的等待时间。

### 执行模式

`execution.mode`

- `parallel`
  - Locust 按任务权重并发混跑。
  - 适合整体吞吐和混合流量压测。
- `serial`
  - 每个虚拟用户按固定默认顺序串行执行一条链路。
  - 适合业务流程验证或单链路压测。
  - 注意：这表示“单个虚拟用户内部串行”，不是“全局只有一个请求串行执行”。
  - 如果希望整体更接近单线程串行，请同时把 `scenarios.vus` 设为 `1`。
- 串行默认顺序固定为：
  - `ping`
  - `auth_login`
  - `auth_me`
  - `books_count`
  - `list_books`
  - `search_books`
  - `book_detail`
  - `favorite_status`
  - `favorite_toggle`
  - `favorites_list`
  - `uploads_list`
  - `download_url`
- 实际执行时，只会运行你在 `enabled_tests` 里勾选为 `true` 的接口。

`init_data.workers`

- 初始化压测数据时的并发 worker 数。
- 采用“用户级并发”：
  - 不同用户之间并行初始化
  - 同一用户内部仍按注册、登录、删旧书、建书链路串行执行
- 这样可以明显加快初始化速度，同时避免同一用户并发建书时撞到后端文件草稿复用逻辑。

### 两种 mock

这里有两层 mock，建议明确区分。

`mock.server_mock`

- 表示这轮压测是否按后端 `server-mock` 模式准备环境。
- 这个值主要用于说明和辅助校验。
- 真正是否启用，仍然由后端仓库的 `config.yaml` 决定：
  - `benchmark.mock_upload_enabled: true`

`mock.upload_mode`

- benchmark 脚本自己的上传行为。
- 可选值：
  - `skip_upload`
    - 不执行真实 PUT 上传，直接走 `complete`
    - 依赖后端开启 `server-mock`
  - `empty_file`
    - 真实 PUT 一个空文件
  - `small_sample`
    - 真实 PUT 一个极小合法样本文件
    - 对 `.epub` 会上传一个最小可解析 epub

建议理解成：

- `server_mock`：后端是否跳过真实上传/解析
- `upload_mode`：脚本自己到底上传什么

### 接口场景开关

`enabled_tests`

- `auth_login`
- `ping`
- `auth_me`
- `books_count`
- `list_books`
- `search_books`
- `book_detail`
- `favorite_status`
- `favorite_toggle`
- `favorites_list`
- `uploads_list`
- `download_url`

当前后端缓存语义下：

- `GET /api/books/count`、`GET /api/books`、`GET /api/books/{id}`
  - 更偏缓存命中场景
- `GET /api/books/search`
  - 当前不走一级缓存，也不走 Redis
  - 更偏数据库搜索压力场景

### 搜索配置

`search_books.mode`

- `fixed`
  - 固定使用 `query`
- `random_from_list`
  - 从 `queries` 中随机挑一个
- `random_generated`
  - 自动生成随机关键字

相关参数：

- `query`
- `queries`
- `generated_min_length`
- `generated_max_length`
- `page`
- `page_size`

## 推荐使用顺序

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 生成初始化数据

```bash
python3 generate_benchmark_data.py
```

3. 初始化账号和书籍

```bash
python3 init_benchmark_data.py
```

4. 启动压测

无头模式：

```bash
locust -f locustfile.py --headless
```

Web UI 模式：

```bash
locust -f locustfile.py
```

5. 或使用 Gradio 控制台

```bash
python3 gradio_app.py
```

默认启动后访问：

- `http://127.0.0.1:7860`
- 控制台里常用参数都已经做成输入框、复选框、下拉框和多行文本框。

## 运行前注意事项

- 后端服务需要先启动。
- 当前登录接口默认依赖验证码开关，压测前建议确认后端 `security.captcha_enabled` 为 `false`。
- 如果 `mock.upload_mode=skip_upload`，必须确保后端开启 `server-mock`，否则 `complete` 会因为对象不存在而失败。
- 如果要观察缓存命中能力，优先开启：
  - `books_count`
  - `list_books`
  - `book_detail`
  - `download_url`
- 如果要观察数据库搜索压力，优先开启：
  - `search_books`
- `favorite_status`、`favorite_toggle`、`favorites_list`、`uploads_list` 都依赖登录态。
- `init_benchmark_data.py` 会先删除当前测试用户下标题以 `压测书籍` 开头的旧书，再重新初始化。

## 报告输出

- Locust 每次压测结束后，会在 `logs/` 下生成中文 Markdown 报告。
- 报告内容包括：
  - 总请求数
  - 失败数
  - 总体 QPS
  - 平均响应时间
  - P95 / P99
  - 各接口统计表
  - 带宽估算（上行/下行/总带宽，单位 Mbps）

## 带宽估算设计

| 设计点 | 说明 |
| --- | --- |
| MTU 1460 | 标准 TCP 以太网 MSS，合理估算分段数 |
| 40 字节头 | 20 IP + 20 TCP，不含选项字段 |
| 线程安全 | 用 `_bandwidth_stats_lock` 保护并发写 |
| 失败请求跳过 | `exception is not None` 时不计入带宽 |
| 不含 TLS 握手 | 仅估算传输阶段，不含连接建立开销 |
