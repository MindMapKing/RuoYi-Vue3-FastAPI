import importlib
import inspect
import os
from pathlib import Path
import sys
from functools import lru_cache
from sqlalchemy import inspect as sa_inspect
from typing import Any, List
from config.database import Base


class ImportUtil:

    @classmethod
    def find_project_root(cls) -> Path:
        """
        查找项目根目录
        1、requirements.txt所在目录就是根目录
        :return: 项目根目录路径
        """
        current_dir = Path(__file__).resolve().parent
        while current_dir != current_dir.parent:
            if any(current_dir.joinpath(file).exists() for file in ['setup.py', 'pyproject.toml', 'requirements.txt']):
                return current_dir
            current_dir = current_dir.parent
        return Path(__file__).resolve().parent

    @classmethod
    def is_valid_model(cls, obj: Any, base_class: Base) -> bool:
        """
        验证是否为有效的SQLAlchemy模型类

        此方法用于验证给定的对象是否为一个有效的SQLAlchemy模型类，通过多重验证确保：
        1. 对象必须是一个类且继承自指定的Base类
        2. 不能是Base基类本身
        3. 必须定义了表名（排除抽象基类）
        4. 必须包含至少一个数据库列定义

        Args:
            obj (Any): 待验证的对象，可能是任何Python对象
            base_class (Base): SQLAlchemy的声明基类，通常为declarative_base()的实例

        Returns:
            bool: 如果对象是有效的SQLAlchemy模型类返回True，否则返回False

        Examples:
            >>> from config.database import Base
            >>> # 假设User是一个有效的模型类
            >>> is_valid = ImportUtil.is_valid_model(User, Base)  # 返回 True
            >>> # 假设SomeClass不是模型类
            >>> is_valid = ImportUtil.is_valid_model(SomeClass, Base)  # 返回 False

        Note:
            此方法主要用于在模型发现过程中过滤掉无效的类定义，
            确保只有真正的数据库模型类被包含在结果中。
        """
        # 第一步验证：检查对象类型和继承关系
        # 确保对象是一个类，继承自指定的Base类，且不是Base基类本身
        if not (inspect.isclass(obj) and issubclass(obj, base_class) and obj is not base_class):
            return False

        # 第二步验证：检查表名定义
        # 排除抽象基类（Abstract Base Class），抽象基类通常不定义__tablename__属性
        if not hasattr(obj, '__tablename__') or obj.__tablename__ is None:
            return False

        # 第三步验证：检查数据库列定义
        # 使用SQLAlchemy的inspect工具检查模型是否包含实际的列定义
        # 这是确保模型可以被正确映射到数据库表的关键验证
        try:
            return len(sa_inspect(obj).columns) > 0
        except Exception:
            # 如果在检查列定义时发生任何异常（如模型定义不完整），
            # 则认为该模型无效
            return False

    @classmethod
    @lru_cache(maxsize=256)
    def find_models(cls, base_class: Base) -> List[Base]:
        """
        查找并过滤有效的模型类，避免重复和无效定义

        :param base_class: SQLAlchemy的Base类，用于验证模型类
        :return: 有效模型类列表
        """
        models = []
        # 按类对象去重
        seen_models = set()
        # 按表名去重（防止同表名冲突）
        seen_tables = set()
        project_root = cls.find_project_root()

        sys.path.append(str(project_root))
        print(f"⏰️ 开始在项目根目录 {project_root} 中查找模型...")

        # 排除目录扩展
        exclude_dirs = {
            'venv',
            '.env',
            '.git',
            '__pycache__',
            'migrations',
            'alembic',
            'tests',
            'test',
            'docs',
            'examples',
            'scripts',
        }

        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    relative_path = Path(root).relative_to(project_root)
                    module_parts = list(relative_path.parts) + [file[:-3]]
                    module_name = '.'.join(module_parts)

                    try:
                        module = importlib.import_module(module_name)

                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            # 验证模型有效性
                            if not cls.is_valid_model(obj, base_class):
                                continue

                            # 检查类对象重复
                            if obj in seen_models:
                                continue

                            # 检查表名重复
                            table_name = obj.__tablename__
                            if table_name in seen_tables:
                                continue

                            seen_models.add(obj)
                            seen_tables.add(table_name)
                            models.append(obj)
                            print(f'✅️ 找到有效模型: {obj.__module__}.{obj.__name__} (表: {table_name})')

                    except ImportError as e:
                        if 'cannot import name' not in str(e):
                            print(f'❗️ 警告: 无法导入模块 {module_name}: {e}')
                    except Exception as e:
                        print(f'❌️ 处理模块 {module_name} 时出错: {e}')

        return models
