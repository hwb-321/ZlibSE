# Benchmark 目录说明

这个目录用于管理后端项目的压测配置、测试账号生成、测试账号初始化，以及 Locust 压测脚本。

## 文件作用

`config.yaml`

- 压测总配置文件。
- 负责定义压测目标地址、普通用户数量、并发用户数、压测时长、等待时间、每个用户初始化多少本书、书籍分页参数、搜索关键字和阈值。

`benchmark_data.yaml`

- 由数据生成脚本产出的压测初始化源数据。
- 默认会被覆盖重写，不做追加。
- 每个用户条目同时包含账号信息和该用户要初始化的书籍列表。

`config_loader.py`

- 负责统一读取 `config.yaml` 和 `benchmark_data.yaml`。
- 为其他脚本提供配置加载和账号列表聚合能力。

`generate_benchmark_data.py`

- 根据 `config.yaml` 中的压测配置生成 `benchmark_data.yaml`。
- 会把账号信息和对应书籍配置一起写入同一个初始化数据文件。

`init_benchmark_data.py`

- 读取 `benchmark_data.yaml`，通过后端注册接口创建测试账号。
- 当前只创建普通用户，不依赖项目内部数据库模型。
- 如果账号已存在，会将其计为已存在并跳过。
- 注册完成后，会登录每个用户并按同一配置文件中的 `books` 列表初始化书籍。

`locustfile.py`

- Locust 压测入口脚本。
- 会读取 `config.yaml` 和 `benchmark_data.yaml`，自动使用测试账号登录并执行核心接口压测。
- 当前覆盖的场景包括登录、书籍列表、书籍搜索、书籍详情、收藏、下载链接获取。
- 每次压测结束后，会把中文结果报告写入 `benchmark/logs/`，包括总体 QPS、平均耗时、P95，以及各接口统计表。

## 推荐使用顺序

1. 生成压测初始化数据

```bash
python3 benchmark/generate_benchmark_data.py
```

2. 初始化全部压测数据

```bash
python3 benchmark/init_benchmark_data.py
```

3. 安装 Locust

```bash
pip install locust
```

4. 启动后端服务

示例：

```bash
python3 -m fastapi_app
```

5. 运行压测

无头模式：

```bash
locust -f benchmark/locustfile.py --headless
```

Web UI 模式：

```bash
locust -f benchmark/locustfile.py
```

## 运行前注意事项

- 当前登录接口默认依赖验证码开关，压测前建议确认业务配置中的 `security.captcha_enabled` 为 `false`。
- 每个测试账号生成多少本书由 `books.books_per_user` 控制，并会写入 `benchmark_data.yaml`。
- 账号和书籍初始化现在共用同一个 `benchmark_data.yaml`，每个用户下的 `books` 列表就是最终初始化源数据。
- 运行 `init_benchmark_data.py` 前，建议先在根目录 `config.yaml` 中将 `benchmark.mock_upload_enabled` 设为 `true`，并确保后端服务已启动。
- `init_benchmark_data.py` 通过 HTTP 调用 `/user/register_user` 创建账号，因此需要后端服务先启动。
