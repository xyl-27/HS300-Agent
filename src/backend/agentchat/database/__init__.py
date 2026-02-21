from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from src.backend.agentchat.database.models.agent import AgentTable
from src.backend.agentchat.database.models.history import HistoryTable
from src.backend.agentchat.database.models.memory_history import MemoryHistoryTable
from src.backend.agentchat.database.models.user import SystemUser
from src.backend.agentchat.database.models.knowledge import KnowledgeTable
from src.backend.agentchat.database.models.knowledge_file import KnowledgeFileTable
from src.backend.agentchat.database.models.tool import ToolTable
from src.backend.agentchat.database.models.dialog import DialogTable
from src.backend.agentchat.database.models.mcp_server import MCPServerTable, MCPServerStdioTable
from src.backend.agentchat.database.models.mcp_user_config import MCPUserConfigTable
from src.backend.agentchat.database.models.mcp_agent import MCPAgentTable
from src.backend.agentchat.database.models.user_role import UserRole
from src.backend.agentchat.database.models.llm import LLMTable
from src.backend.agentchat.database.models.message import MessageDownTable, MessageLikeTable
from src.backend.agentchat.database.models.role import Role
from src.backend.agentchat.database.models.workspace_session import WorkSpaceSession
from src.backend.agentchat.database.models.usage_stats import UsageStats
from src.backend.agentchat.database.models.stock import StockInfo, StockDaily

from src.backend.agentchat.settings import app_settings
from src.backend.agentchat.settings import initialize_app_settings
import asyncio
import logging

from dotenv import load_dotenv

# 初始化logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# 加载本地的env
load_dotenv(override=True)

# 加载配置文件
# 使用绝对路径加载配置文件
import os
config_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
asyncio.run(initialize_app_settings(config_file_path))
logger.info(f"配置文件加载路径: {config_file_path}")
logger.info(f"配置文件是否存在: {os.path.exists(config_file_path)}")

# 确保mysql配置存在
if not app_settings.mysql:
    app_settings.mysql = {
        'endpoint': 'mysql+pymysql://root:qwe123@localhost:3306/agentchat',
        'async_endpoint': 'mysql+aiomysql://root:qwe123@localhost:3306/agentchat'
    }

# 打印数据库配置信息
logger.info(f"数据库配置: {app_settings.mysql}")
logger.info(f"数据库连接地址: {app_settings.mysql.get('endpoint')}")

# 尝试创建数据库
import pymysql

endpoint = app_settings.mysql.get('endpoint')
if endpoint:
    # 解析数据库连接参数
    import re
    # 修复正则表达式，确保能够正确解析数据库名称
    match = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)', endpoint)
    if match:
        user, password, host, port, db_name = match.groups()
        logger.info(f"解析数据库连接参数: user={user}, host={host}, port={port}, db_name={db_name}")
        
        # 尝试连接到MySQL服务器并创建数据库
        try:
            logger.info(f"尝试连接到MySQL服务器并创建数据库 {db_name}...")
            # 先连接到MySQL服务器（不指定数据库）
            conn = pymysql.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            # 创建数据库（简化SQL语句，避免语法错误）
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"数据库 {db_name} 创建成功!")
        except Exception as e:
            logger.error(f"创建数据库失败: {e}")
            logger.exception(e)
    else:
        logger.error(f"无法解析数据库连接地址: {endpoint}")
else:
    logger.error("数据库连接地址为空")

# 创建数据库引擎
engine = create_engine(app_settings.mysql.get('endpoint'),
                       pool_pre_ping=True, # 连接前检查其有效性
                       pool_recycle=3600, # 每隔1小时进行重连一次
                       connect_args={"charset": "utf8mb4",
                                     "use_unicode": True,
                                     'init_command': "SET SESSION time_zone = '+08:00'"})

async_engine = create_async_engine(app_settings.mysql.get('async_endpoint'),
                                   pool_pre_ping=True,  # 连接前检查其有效性
                                   pool_recycle=3600,  # 每隔1小时进行重连一次
                                   connect_args={"charset": "utf8mb4",
                                                 "use_unicode": True,
                                                 'init_command': "SET SESSION time_zone = '+08:00'"})

# 创建数据库表
logger.info("创建数据库表...")
SQLModel.metadata.create_all(engine)
logger.info("数据库表创建成功!")
