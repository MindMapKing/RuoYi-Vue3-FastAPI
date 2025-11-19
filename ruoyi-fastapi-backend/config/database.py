# 导入 SQLAlchemy 相关模块
from sqlalchemy.ext.asyncio import create_async_engine  # 创建异步数据库引擎
from sqlalchemy.ext.asyncio import async_sessionmaker   # 创建异步会话工厂
from sqlalchemy.ext.asyncio import AsyncAttrs           # 异步属性支持基类
from sqlalchemy.orm import DeclarativeBase             # 声明式基类，用于模型定义
from urllib.parse import quote_plus                     # URL 编码工具，用于转义特殊字符
from config.env import DataBaseConfig                  # 导入数据库配置

# 构建异步数据库连接URL
# 默认使用 MySQL 数据库连接字符串格式
ASYNC_SQLALCHEMY_DATABASE_URL = (
    f'mysql+asyncmy://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
    f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
)

# 如果数据库类型为 PostgreSQL，则使用 PostgreSQL 连接字符串格式
if DataBaseConfig.db_type == 'postgresql':
    ASYNC_SQLALCHEMY_DATABASE_URL = (
        f'postgresql+asyncpg://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )

# 创建异步数据库引擎
# 引擎负责管理数据库连接池和与数据库的通信
async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,                    # 数据库连接URL
    echo=DataBaseConfig.db_echo,                      # 是否在控制台打印SQL语句，用于调试
    max_overflow=DataBaseConfig.db_max_overflow,      # 连接池溢出时允许的最大额外连接数
    pool_size=DataBaseConfig.db_pool_size,            # 连接池保持的连接数
    pool_recycle=DataBaseConfig.db_pool_recycle,      # 连接回收时间（秒），防止连接长时间不活跃被服务器关闭
    pool_timeout=DataBaseConfig.db_pool_timeout,      # 从连接池获取连接的超时时间
)

# 创建异步会话工厂
# 会话工厂用于创建数据库会话，会话是执行数据库操作的上下文管理器
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,     # 关闭自动提交，需要手动提交事务
    autoflush=False,      # 关闭自动刷新，需要手动刷新会话
    bind=async_engine     # 绑定到数据库引擎
)


# 定义所有数据库模型的基类
# 继承 AsyncAttrs 支持异步属性访问，继承 DeclarativeBase 提供声明式模型定义功能
class Base(AsyncAttrs, DeclarativeBase):
    """
    数据库模型基类

    所有数据库模型都应该继承此基类，它会提供：
    - 异步属性支持（通过 AsyncAttrs）
    - 声明式模型定义功能（通过 DeclarativeBase）
    - 自动表名生成和元数据管理
    """
    pass
