# ZlibSE Backend Refactor TODO

## 目标
- 重构后端目录结构，避免所有逻辑继续堆在 `fastapi_app/main.py`
- 保留当前数据库实现，不立即切换数据库类型
- 引入 ORM 分层和仓储抽象，尽量抹平未来从 SQLite 切换到 PostgreSQL 的差异
- 文件存储改为面向 S3 的设计，上传和下载采用签名 URL
- 认证方案从 Session 切换为 JWT

## 阶段 1：重构目录结构
- [ ] 新建清晰的后端分层目录
- [ ] 将接口按领域拆分到 `routers/`
- [ ] 将核心业务逻辑拆分到 `services/`
- [ ] 将数据库访问拆分到 `repositories/` 或 `crud/`
- [ ] 将 ORM 模型放入 `models/`
- [ ] 将请求/响应模型放入 `schemas/`
- [ ] 将配置、鉴权、依赖注入、存储客户端放入 `core/`
- [ ] 保留一个足够薄的 `main.py`，只负责应用组装和路由注册

## 建议目录
```text
fastapi_app/
  main.py
  core/
    config.py
    database.py
    security.py
    deps.py
    storage.py
  models/
    user.py
    book.py
  schemas/
    auth.py
    book.py
    user.py
  repositories/
    user_repository.py
    book_repository.py
    favorite_repository.py
    upload_repository.py
  services/
    auth_service.py
    book_service.py
    favorite_service.py
    upload_service.py
    storage_service.py
  routers/
    auth.py
    books.py
    favorites.py
    uploads.py
    users.py
```

## 阶段 2：数据库与 ORM 抽象
- [ ] 保留 SQLite，继续使用 SQLAlchemy
- [ ] 明确数据库相关代码只通过 `repositories/` 访问，不在路由层直接写查询
- [ ] 统一 ORM 模型风格，避免把业务逻辑写进接口函数
- [ ] 补齐通用数据库依赖和事务边界
- [ ] 将“文件路径”字段抽象成存储元数据，避免继续绑定本地磁盘路径
- [ ] 设计可迁移的数据字段，例如：
  - `storage_provider`
  - `bucket`
  - `object_key`
  - `cover_object_key`
  - `original_filename`
  - `content_type`
  - `file_size`
- [ ] 尽量避免使用 SQLite 专属写法，后续切库时优先只改配置和迁移脚本
- [ ] 引入 Alembic，后续表结构调整通过迁移管理

## 阶段 3：JWT 认证替换 Session
- [ ] 移除基于 `SessionMiddleware` 的登录态方案
- [ ] 新增 JWT 生成与校验逻辑
- [ ] 设计 `access_token`
- [ ] 视需求决定是否同时引入 `refresh_token`
- [ ] 登录接口改为返回 token，而不是写 session
- [ ] 受保护接口统一通过 `Authorization: Bearer <token>` 鉴权
- [ ] 抽出 `get_current_user` 依赖，基于 JWT 解出用户身份
- [ ] 明确 token 过期时间、签名算法、密钥来源和刷新策略
- [ ] 将密码哈希逻辑保留在独立安全模块

## 阶段 4：S3 存储接入
- [ ] 抽象统一存储接口，屏蔽“本地存储 / S3 存储”的实现差异
- [ ] 定义 `StorageService`，至少包含：
  - `create_upload_url`
  - `create_download_url`
  - `delete_object`
  - `build_public_meta`
- [ ] 后端不再直接接收大文件并落盘
- [ ] 上传流程改为：
  1. 前端请求后端创建上传签名 URL
  2. 后端生成 S3 预签名上传 URL
  3. 前端直传到 S3
  4. 前端回调后端保存书籍元数据
- [ ] 下载流程改为：
  1. 前端请求下载某本书
  2. 后端校验权限
  3. 后端生成 S3 预签名下载 URL
  4. 前端跳转或拉取该 URL
- [ ] 封面图与电子书统一走对象存储，不再使用本地 `media/`
- [ ] 明确对象命名规则，避免文件覆盖和脏数据

## 阶段 5：接口重构
- [ ] 用户相关接口统一归类到 `routers/auth.py` 与 `routers/users.py`
- [ ] 图书相关接口统一归类到 `routers/books.py`
- [ ] 收藏相关接口统一归类到 `routers/favorites.py`
- [ ] 上传记录与修改删除相关接口统一归类到 `routers/uploads.py`
- [ ] 为每个接口补充 Pydantic 请求/响应模型
- [ ] 统一错误返回结构
- [ ] 统一成功返回结构
- [ ] 清理当前接口中的乱码提示文案

## 阶段 6：配置管理
- [ ] 新增统一配置模块，以 YAML 配置文件为主
- [ ] 明确区分 `config.dev.yaml`、`config.prod.yaml` 等环境配置文件
- [ ] 约定配置加载顺序，例如：默认 YAML -> 环境 YAML -> 少量环境变量覆盖
- [ ] 配置项至少包含：
  - `DATABASE_URL`
  - `JWT_SECRET_KEY`
  - `JWT_ALGORITHM`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`
  - `S3_ENDPOINT`
  - `S3_ACCESS_KEY`
  - `S3_SECRET_KEY`
  - `S3_BUCKET`
  - `S3_REGION`
- [ ] 在 `core/config.py` 中统一读取、校验和缓存配置
- [ ] 避免在业务代码里直接读取配置文件或环境变量

## 阶段 7：数据模型与业务规则梳理
- [ ] 梳理 `User`、`Book`、`UploadedBook`、`UserCollectedBook` 的职责边界
- [ ] 明确管理员和普通用户的权限差异
- [ ] 明确书籍删除时的级联策略
- [ ] 明确收藏、上传记录的唯一性约束
- [ ] 明确书籍修改时是否允许替换对象存储中的源文件

## 阶段 8：测试与验证
- [ ] 为鉴权流程补测试：注册、登录、JWT 校验、过期 token、非法 token
- [ ] 为图书流程补测试：创建上传 URL、保存元数据、列表、详情、删除
- [ ] 为收藏流程补测试：新增、取消、重复收藏
- [ ] 为权限流程补测试：普通用户与管理员的差异
- [ ] 为存储流程补测试：签名 URL 生成、对象删除、异常处理

## 阶段 9：迁移顺序建议
- [ ] 第一步：重构目录，不改业务行为
- [ ] 第二步：抽离 repository/service，稳定 ORM 访问边界
- [ ] 第三步：切换认证为 JWT
- [ ] 第四步：引入存储抽象，保留本地实现作为过渡
- [ ] 第五步：接入 S3 预签名 URL
- [ ] 第六步：删除旧的本地文件直传逻辑和 Session 依赖

## 当前优先做的 5 件事
- [ ] 拆分 `main.py`，先落 `routers/`、`services/`、`repositories/`
- [ ] 抽象数据库访问层，避免接口层直接写 SQLAlchemy 查询
- [ ] 定义 JWT 认证模块和统一鉴权依赖
- [ ] 设计书籍文件的对象存储字段，不再依赖本地文件路径
- [ ] 设计 S3 预签名上传/下载接口协议
