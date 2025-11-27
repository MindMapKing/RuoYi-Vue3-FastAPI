"""
数据库配置模块

该模块负责配置和初始化数据库连接，支持MySQL和PostgreSQL两种数据库。
使用SQLAlchemy异步ORM引擎，提供数据库会话管理和基础模型类。

主要功能：
1. 根据配置动态生成数据库连接URL
2. 创建异步数据库引擎
3. 配置数据库连接池参数
4. 提供异步会话工厂
5. 定义基础模型类供其他实体继承
"""

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import quote_plus
from config.env import DataBaseConfig

# 数据库连接URL配置
# 根据数据库类型动态生成异步数据库连接字符串
# 默认使用MySQL数据库，使用asyncmy异步驱动
ASYNC_SQLALCHEMY_DATABASE_URL = (
    f'mysql+asyncmy://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
    f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
)

# 根据配置判断是否使用PostgreSQL数据库
# PostgreSQL使用asyncpg异步驱动，性能更优
if DataBaseConfig.db_type == 'postgresql':
    ASYNC_SQLALCHEMY_DATABASE_URL = (
        f'postgresql+asyncpg://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )

# 异步数据库引擎配置
# 创建支持异步操作的SQLAlchemy引擎，用于数据库连接和操作
async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    echo=DataBaseConfig.db_echo,                              # 是否打印SQL语句，开发环境建议开启
    max_overflow=DataBaseConfig.db_max_overflow,             # 连接池最大溢出连接数
    pool_size=DataBaseConfig.db_pool_size,                   # 连接池基础连接数
    pool_recycle=DataBaseConfig.db_pool_recycle,             # 连接回收时间（秒），防止连接过期
    pool_timeout=DataBaseConfig.db_pool_timeout,             # 获取连接超时时间（秒）
)

# 异步数据库会话工厂
# 创建用于异步数据库操作的会话工厂，autocommit和autoflush关闭确保事务可控性
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=async_engine)


class Base(AsyncAttrs, DeclarativeBase):
    """
    基础模型类

    所有数据库实体类的基类，继承自SQLAlchemy的DeclarativeBase和AsyncAttrs。
    提供异步属性访问支持和ORM映射功能。

    继承此类的子类将自动获得：
    1. SQLAlchemy ORM映射能力
    2. 异步属性访问支持
    3. 数据库表结构定义能力
    4. 声明式模型定义功能

    使用示例：
        class User(Base):
            __tablename__ = "sys_user"
            id = Column(Integer, primary_key=True)
            username = Column(String(50))
    """
    pass
