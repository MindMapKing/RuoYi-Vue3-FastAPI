import json
# APScheduler 事件常量：监听所有类型的事件（执行、异常、提交等）
from apscheduler.events import EVENT_ALL
# 异步 IO 执行器：用于调度异步协程任务
from apscheduler.executors.asyncio import AsyncIOExecutor
# 进程池执行器：在独立进程中运行任务，隔离资源
from apscheduler.executors.pool import ProcessPoolExecutor
# 内存型任务存储：任务仅保存在内存，重启即丢失
from apscheduler.jobstores.memory import MemoryJobStore
# Redis 任务存储：将任务持久化到 Redis，支持分布式
from apscheduler.jobstores.redis import RedisJobStore
# SQLAlchemy 任务存储：将任务持久化到数据库，支持跨重启
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
# 异步 IO 调度器：基于 asyncio 的主调度引擎
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# 组合触发器：可将多个触发器“或”在一起，满足其一即触发
from apscheduler.triggers.combining import OrTrigger
# Cron 触发器：按类 Unix crontab 表达式周期性触发
from apscheduler.triggers.cron import CronTrigger
# 一次性日期触发器：在指定时间点触发一次
from apscheduler.triggers.date import DateTrigger
# 引入 asyncio 的 iscoroutinefunction，用于判断一个函数是否为异步协程函数
# 在 add_scheduler_job 与 execute_scheduler_job_once 中，若目标函数是协程，则强制使用 AsyncIOExecutor('default') 执行器
from asyncio import iscoroutinefunction
from datetime import datetime, timedelta
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Union
from config.database import AsyncSessionLocal, quote_plus
from config.env import DataBaseConfig, RedisConfig
from module_admin.dao.job_dao import JobDao
from module_admin.entity.vo.job_vo import JobLogModel, JobModel
from module_admin.service.job_log_service import JobLogService
from utils.log_util import logger
import module_task  # noqa: F401


# 重写Cron定时
class MyCronTrigger(CronTrigger):
    @classmethod
    @classmethod
    def from_crontab(cls, expr: str, timezone=None):
        """
        类方法：将 6 或 7 位 crontab 表达式解析为 MyCronTrigger 实例。
        cls 是类本身（MyCronTrigger），用于在类方法内部创建并返回当前类的实例。
        """
        values = expr.split()
        if len(values) != 6 and len(values) != 7:
            raise ValueError('Wrong number of fields; got {}, expected 6 or 7'.format(len(values)))

        second = values[0]
        minute = values[1]
        hour = values[2]
        if '?' in values[3]:
            day = None
        elif 'L' in values[5]:
            day = f"last {values[5].replace('L', '')}"
        elif 'W' in values[3]:
            day = cls.__find_recent_workday(int(values[3].split('W')[0]))
        else:
            day = values[3].replace('L', 'last')
        month = values[4]
        if '?' in values[5] or 'L' in values[5]:
            week = None
        elif '#' in values[5]:
            week = int(values[5].split('#')[1])
        else:
            week = values[5]
        if '#' in values[5]:
            day_of_week = int(values[5].split('#')[0]) - 1
        else:
            day_of_week = None
        year = values[6] if len(values) == 7 else None
        return cls(
            second=second,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            week=week,
            day_of_week=day_of_week,
            year=year,
            timezone=timezone,
        )

    @classmethod
    def __find_recent_workday(cls, day: int):
        now = datetime.now()
        date = datetime(now.year, now.month, day)
        if date.weekday() < 5:
            return date.day
        else:
            diff = 1
            while True:
                previous_day = date - timedelta(days=diff)
                if previous_day.weekday() < 5:
                    return previous_day.day
                else:
                    diff += 1


SQLALCHEMY_DATABASE_URL = (
    f'mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
    f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
)
if DataBaseConfig.db_type == 'postgresql':
    SQLALCHEMY_DATABASE_URL = (
        f'postgresql+psycopg2://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=DataBaseConfig.db_echo,
    max_overflow=DataBaseConfig.db_max_overflow,
    pool_size=DataBaseConfig.db_pool_size,
    pool_recycle=DataBaseConfig.db_pool_recycle,
    pool_timeout=DataBaseConfig.db_pool_timeout,
)
# SessionLocal 是一个 SQLAlchemy 的同步会话工厂，用于在同步代码（如 scheduler_event_listener）中
# 获取数据库会话，以便将任务日志写入数据库。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
job_stores = {
    'default': MemoryJobStore(),
    'sqlalchemy': SQLAlchemyJobStore(url=SQLALCHEMY_DATABASE_URL, engine=engine),
    'redis': RedisJobStore(
        **dict(
            host=RedisConfig.redis_host,
            port=RedisConfig.redis_port,
            username=RedisConfig.redis_username,
            password=RedisConfig.redis_password,
            db=RedisConfig.redis_database,
        )
    ),
}
executors = {'default': AsyncIOExecutor(), 'processpool': ProcessPoolExecutor(5)}
job_defaults = {'coalesce': False, 'max_instance': 1}
scheduler = AsyncIOScheduler()
scheduler.configure(jobstores=job_stores, executors=executors, job_defaults=job_defaults)


class SchedulerUtil:
    """
    定时任务相关方法
    """

    @classmethod
    async def init_system_scheduler(cls):
        """
        应用启动时初始化定时任务

        :return:
        """
        logger.info('🔎 开始启动定时任务...')
        scheduler.start()
        async with AsyncSessionLocal() as session:
            job_list = await JobDao.get_job_list_for_scheduler(session)
            for item in job_list:
                cls.remove_scheduler_job(job_id=str(item.job_id))
                cls.add_scheduler_job(item)
        scheduler.add_listener(cls.scheduler_event_listener, EVENT_ALL)
        logger.info('✅️ 系统初始定时任务加载成功')

    @classmethod
    async def close_system_scheduler(cls):
        """
        应用关闭时关闭定时任务

        :return:
        """
        scheduler.shutdown()
        logger.info('✅️ 关闭定时任务成功')

    @classmethod
    def get_scheduler_job(cls, job_id: Union[str, int]):
        """
        根据任务id获取任务对象

        :param job_id: 任务id
        :return: 任务对象
        """
        query_job = scheduler.get_job(job_id=str(job_id))

        return query_job

    @classmethod
    def add_scheduler_job(cls, job_info: JobModel):
        """
        根据输入的任务对象信息添加任务

        :param job_info: 任务对象信息
        :return:
        """
        job_func = eval(job_info.invoke_target)
        job_executor = job_info.job_executor
        if iscoroutinefunction(job_func):
            job_executor = 'default'
        scheduler.add_job(
            func=eval(job_info.invoke_target),
            trigger=MyCronTrigger.from_crontab(job_info.cron_expression),
            args=job_info.job_args.split(',') if job_info.job_args else None,
            kwargs=json.loads(job_info.job_kwargs) if job_info.job_kwargs else None,
            id=str(job_info.job_id),
            name=job_info.job_name,
            misfire_grace_time=1000000000000 if job_info.misfire_policy == '3' else None,
            coalesce=True if job_info.misfire_policy == '2' else False,
            max_instances=3 if job_info.concurrent == '0' else 1,
            jobstore=job_info.job_group,
            executor=job_executor,
        )

    @classmethod
    def execute_scheduler_job_once(cls, job_info: JobModel):
        """
        根据输入的任务对象执行一次任务

        :param job_info: 任务对象信息
        :return:
        """
        job_func = eval(job_info.invoke_target)
        job_executor = job_info.job_executor
        if iscoroutinefunction(job_func):
            job_executor = 'default'
        job_trigger = DateTrigger()
        if job_info.status == '0':
            job_trigger = OrTrigger(triggers=[DateTrigger(), MyCronTrigger.from_crontab(job_info.cron_expression)])
        scheduler.add_job(
            func=eval(job_info.invoke_target),
            trigger=job_trigger,
            args=job_info.job_args.split(',') if job_info.job_args else None,
            kwargs=json.loads(job_info.job_kwargs) if job_info.job_kwargs else None,
            id=str(job_info.job_id),
            name=job_info.job_name,
            misfire_grace_time=1000000000000 if job_info.misfire_policy == '3' else None,
            coalesce=True if job_info.misfire_policy == '2' else False,
            max_instances=3 if job_info.concurrent == '0' else 1,
            jobstore=job_info.job_group,
            executor=job_executor,
        )

    @classmethod
    def remove_scheduler_job(cls, job_id: Union[str, int]):
        """
        根据任务id移除任务

        :param job_id: 任务id
        :return:
        """
        query_job = cls.get_scheduler_job(job_id=job_id)
        if query_job:
            scheduler.remove_job(job_id=str(job_id))

    @classmethod
    def scheduler_event_listener(cls, event):
        """
        APScheduler 事件监听器：当调度器产生任何事件（任务提交、执行成功、执行异常等）时被回调，
        负责把事件的核心信息落库到 sys_job_log 表，方便后台查看任务执行历史与异常原因。
        """
        # 获取事件类型和任务ID
        event_type = event.__class__.__name__
        # 获取任务执行异常信息
        status = '0'
        exception_info = ''
        if event_type == 'JobExecutionEvent' and event.exception:
            exception_info = str(event.exception)
            status = '1'
        if hasattr(event, 'job_id'):
            job_id = event.job_id
            query_job = cls.get_scheduler_job(job_id=job_id)
            if query_job:
                query_job_info = query_job.__getstate__()
                # 获取任务名称
                job_name = query_job_info.get('name')
                # 获取任务组名
                job_group = query_job._jobstore_alias
                # 获取任务执行器
                job_executor = query_job_info.get('executor')
                # 获取调用目标字符串
                invoke_target = query_job_info.get('func')
                # 获取调用函数位置参数
                job_args = ','.join(query_job_info.get('args'))
                # 获取调用函数关键字参数
                job_kwargs = json.dumps(query_job_info.get('kwargs'))
                # 获取任务触发器
                job_trigger = str(query_job_info.get('trigger'))
                # 构造日志消息
                job_message = f"事件类型: {event_type}, 任务ID: {job_id}, 任务名称: {job_name}, 执行于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                job_log = JobLogModel(
                    jobName=job_name,
                    jobGroup=job_group,
                    jobExecutor=job_executor,
                    invokeTarget=invoke_target,
                    jobArgs=job_args,
                    jobKwargs=job_kwargs,
                    jobTrigger=job_trigger,
                    jobMessage=job_message,
                    status=status,
                    exceptionInfo=exception_info,
                    createTime=datetime.now(),
                )
                session = SessionLocal()
                JobLogService.add_job_log_services(session, job_log)
                session.close()
