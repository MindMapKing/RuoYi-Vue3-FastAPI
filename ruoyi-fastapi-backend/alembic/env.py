import asyncio
import os
from alembic import context
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from config.database import Base, ASYNC_SQLALCHEMY_DATABASE_URL
from utils.import_util import ImportUtil


# ============================================================================
# 初始化配置
# ============================================================================

# 确保迁移版本目录存在
# alembic/versions 目录用于存储所有数据库迁移脚本文件
alembic_veresions_path = 'alembic/versions'
if not os.path.exists(alembic_veresions_path):
    os.makedirs(alembic_veresions_path)


# 自动发现并加载项目中所有的SQLAlchemy模型类
# ImportUtil.find_models() 会扫描整个项目，查找所有继承自Base的有效模型类
# 这是实现自动迁移检测的关键步骤，确保所有模型都被包含在元数据中
found_models = ImportUtil.find_models(Base)

# ============================================================================
# Alembic 配置设置
# ============================================================================

# 获取 Alembic 配置对象
# 该对象提供了对 alembic.ini 配置文件中所有值的访问权限
alembic_config = context.config

# 配置 Python 日志系统
# 根据配置文件设置日志记录器，用于迁移过程中的日志输出
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# 设置目标元数据对象
# Base.metadata 包含了所有已注册模型类的元数据信息
# 这是实现自动生成迁移文件（autogenerate）的关键组件
target_metadata = Base.metadata

# 动态设置数据库连接URL
# 从应用的数据库配置中获取异步数据库连接字符串，并覆盖 alembic.ini 中的默认配置
# 这确保了迁移工具使用与应用相同的数据库连接配置
alembic_config.set_main_option('sqlalchemy.url', ASYNC_SQLALCHEMY_DATABASE_URL)


# ============================================================================
# 离线模式迁移执行
# ============================================================================

def run_migrations_offline() -> None:
    """
    在离线模式下运行数据库迁移

    离线模式特点：
    - 只需要数据库URL，不需要实际的数据库连接
    - 不需要DBAPI驱动程序可用
    - 通过跳过Engine创建来减少依赖
    - 适用于无法连接到目标数据库的环境（如CI/CD流水线）

    迁移操作：
    - context.execute() 的输出会直接打印到脚本输出
    - 生成SQL脚本而不是直接执行数据库操作
    """
    # 获取数据库连接URL
    url = alembic_config.get_main_option('sqlalchemy.url')

    # 配置离线模式迁移上下文
    context.configure(
        url=url,                                    # 数据库连接URL
        target_metadata=target_metadata,            # 目标模型元数据
        literal_binds=True,                         # 使用字面量绑定，生成可直接执行的SQL
        dialect_opts={'paramstyle': 'named'},      # 使用命名参数风格
    )

    # 在事务上下文中执行迁移
    with context.begin_transaction():
        context.run_migrations()


# ============================================================================
# 在线模式迁移执行核心逻辑
# ============================================================================

def do_run_migrations(connection: Connection) -> None:
    """
    执行在线模式迁移的核心逻辑

    该函数配置并运行实际的数据库迁移操作，包含智能检测机制
    """
    def process_revision_directives(context, revision, directives):
        """
        处理迁移指令的回调函数

        该函数用于智能检测模型变更，避免生成空的迁移文件
        """
        script = directives[0]

        # 检查所有升级操作集是否为空
        # 通过遍历所有的upgrade_ops_list来判断是否有实际的数据库变更
        all_empty = all(ops.is_empty() for ops in script.upgrade_ops_list)

        if all_empty:
            # 如果没有检测到任何模型变更，则清空指令列表，不生成迁移文件
            # 这避免了创建无意义的空迁移文件
            directives[:] = []
            print('❎️ 未检测到模型变更，不生成迁移文件')
        else:
            # 检测到模型变更，继续生成迁移文件
            print('✅️ 检测到模型变更，生成迁移文件')

    # 配置在线模式迁移上下文
    context.configure(
        connection=connection,                        # 数据库连接对象
        target_metadata=target_metadata,             # 目标模型元数据
        compare_type=True,                           # 比较列类型变更
        compare_server_default=True,                 # 比较默认值变更
        transaction_per_migration=True,              # 每个迁移使用独立事务
        process_revision_directives=process_revision_directives,  # 指令处理回调
    )

    # 在事务上下文中执行迁移
    with context.begin_transaction():
        context.run_migrations()


# ============================================================================
# 异步在线模式迁移执行
# ============================================================================

async def run_async_migrations() -> None:
    """
    异步执行在线模式的数据库迁移

    该函数创建异步数据库引擎并执行迁移操作：
    1. 根据配置创建异步SQLAlchemy引擎
    2. 建立数据库连接
    3. 调用同步迁移执行函数
    4. 清理连接资源

    使用场景：
    - 适用于异步FastAPI应用的数据库迁移
    - 支持异步数据库驱动（asyncmy、asyncpg等）
    """
    # 创建异步数据库引擎
    # 使用NullPool避免连接池复用，确保迁移过程中的连接隔离
    connectable = async_engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix='sqlalchemy.',                       # 配置前缀
        poolclass=pool.NullPool,                    # 使用空连接池
    )

    # 建立异步数据库连接并执行迁移
    async with connectable.connect() as connection:
        # 将异步连接传递给同步迁移执行函数
        await connection.run_sync(do_run_migrations)

    # 清理数据库引擎资源
    await connectable.dispose()


# ============================================================================
# 入口函数
# ============================================================================

def run_migrations_online() -> None:
    """
    在线模式迁移入口函数

    该函数是在线模式迁移的入口点，负责启动异步迁移执行流程
    """
    # 启动异步迁移执行
    asyncio.run(run_async_migrations())


# ============================================================================
# 主执行逻辑
# ============================================================================

# 根据Alembic上下文模式选择执行方式
# context.is_offline_mode() 判断当前是否为离线模式
# - 离线模式：生成SQL脚本文件，不直接执行数据库操作
# - 在线模式：直接连接数据库执行迁移操作
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
