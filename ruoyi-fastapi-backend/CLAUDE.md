# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 FastAPI + SQLAlchemy 的后端项目（RuoYi-Vue3-FastAPI），使用分层架构设计，包含系统管理、代码生成、定时任务等功能模块。

## 启动和运行命令

### 开发环境启动
```bash
python app.py
```

### 数据库迁移（Alembic）
```bash
# 创建迁移文件
alembic revision --autogenerate -m "描述信息"

# 执行迁移
alembic upgrade head

# 降级迁移
alembic downgrade -1
```

### 环境配置
- 开发环境：`.env.dev`（默认）
- 生产环境：`.env.prod`
- 通过 `--env` 参数或环境变量 `APP_ENV` 切换

## 项目架构

### 核心目录结构
```
├── app.py                    # 应用入口点
├── server.py                 # FastAPI 应用初始化和配置
├── config/                   # 配置模块
│   ├── env.py               # 环境配置（使用 @lru_cache 进行本地缓存）
│   ├── database.py          # 数据库配置
│   ├── get_db.py            # 数据库连接初始化
│   ├── get_redis.py         # Redis 连接初始化
│   └── get_scheduler.py     # 定时任务初始化
├── module_admin/            # 系统管理模块
│   ├── controller/          # 控制器层（API 端点）
│   ├── service/             # 业务逻辑层
│   ├── dao/                 # 数据访问层
│   ├── entity/              # 实体类
│   │   ├── do/             # 数据库对象
│   │   └── vo/             # 视图对象
│   ├── annotation/          # 注解（日志、验证等）
│   └── aspect/             # 切面（数据权限、接口认证）
├── module_generator/        # 代码生成模块
├── module_task/            # 定时任务模块
├── middlewares/            # 中间件
├── exceptions/             # 异常处理
├── utils/                  # 工具类
└── alembic/               # 数据库迁移文件
```

### 分层架构模式
- **Controller**: 处理 HTTP 请求和响应，使用 FastAPI 路由
- **Service**: 业务逻辑层，处理复杂的业务规则
- **DAO (Data Access Object)**: 数据访问层，封装数据库操作
- **Entity**: 数据模型，分为 DO（数据库对象）和 VO（视图对象）

### 技术栈特性
- **异步编程**: 使用 async/await 模式
- **ORM**: SQLAlchemy 2.0 with async support
- **数据库**: 支持 MySQL 和 PostgreSQL
- **缓存**: Redis 用于会话和系统缓存
- **定时任务**: APScheduler
- **代码生成**: 基于数据库表自动生成 CRUD 代码
- **日志**: loguru 日志框架

## 配置系统

### 环境配置类
项目使用 Pydantic Settings 进行配置管理：
- `AppSettings`: 应用基础配置
- `JwtSettings`: JWT 认证配置
- `DataBaseSettings`: 数据库连接配置
- `RedisSettings`: Redis 连接配置

### 本地缓存机制
配置类使用 `@lru_cache()` 装饰器实现本地缓存，避免重复读取配置文件。

## 数据库支持

### 双数据库支持
- MySQL: 使用 `asyncmy` 驱动
- PostgreSQL: 使用 `asyncpg` 驱动

### 数据库 URL 拼接规则
项目使用自定义的数据库 URL 拼接逻辑，根据 `db_type` 选择对应的驱动和连接字符串格式。

## 中间件系统

- **CORS 中间件**: 跨域请求处理
- **Gzip 中间件**: 响应压缩
- **Trace 中间件**: 请求链路追踪

## 异常处理

统一的异常处理机制，在 `exceptions/handle.py` 中定义全局异常处理器。

## 定时任务

使用 APScheduler 实现定时任务，支持同步和异步函数执行。示例代码在 `module_task/scheduler_test.py`。

## 代码生成

内置代码生成器，可以根据数据库表自动生成完整的 CRUD 代码，包括 Controller、Service、DAO、Entity 等。