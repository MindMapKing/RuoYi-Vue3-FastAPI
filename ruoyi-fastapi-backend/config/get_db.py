from config.database import async_engine, AsyncSessionLocal, Base
from utils.log_util import logger


async def get_db():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接

    :return:
    """
    # yield 把 current_db 交给 FastAPI 的依赖注入系统，
    # 在请求生命周期内保持会话打开，请求结束后自动关闭。
    async with AsyncSessionLocal() as current_db:
        yield current_db


async def init_create_table():
    """
    应用启动时根据所有已注册的 ORM 模型（Base 子类）自动在数据库中创建对应的表。
    如果表已存在则跳过，不会重建；因此也可用于“建表”而非“建库”。
    注意：它并不建立“连接池”或“会话工厂”，只是确保表结构就绪。
    """
    logger.info('🔎 开始自动创建/同步数据库表结构...')
    async with async_engine.begin() as conn:
        # 利用 SQLAlchemy 的 metadata.create_all 一次性创建所有表
        await conn.run_sync(Base.metadata.create_all)
    logger.info('✅️ 数据库表结构同步完成')
