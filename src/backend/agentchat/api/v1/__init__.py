from fastapi import APIRouter
from .agent import router as agent_router
from .chat import router as chat_router
from .dialog import router as dialog_router
from .history import router as history_router
from .knowledge import router as knowledge_router
from .knowledge_file import router as knowledge_file_router
from .lingseek import router as lingseek_router
from .llm import router as llm_router
from .mars import router as mars_router
from .mcp_agent import router as mcp_agent_router
from .mcp_chat import router as mcp_chat_router
from .mcp_server import router as mcp_server_router
from .mcp_stdio_server import router as mcp_stdio_server_router
from .mcp_user_config import router as mcp_user_config_router
from .message import router as message_router
from .tool import router as tool_router
from .upload import router as upload_router
from .usage_stats import router as usage_stats_router
from .user import router as user_router
from .wechat import router as wechat_router
from .workspace import router as workspace_router
from .stock import router as stock_router

router = APIRouter()
router.include_router(agent_router)
router.include_router(chat_router)
router.include_router(dialog_router)
router.include_router(history_router)
router.include_router(knowledge_router)
router.include_router(knowledge_file_router)
router.include_router(lingseek_router)
router.include_router(llm_router)
router.include_router(mars_router)
router.include_router(mcp_agent_router)
router.include_router(mcp_chat_router)
router.include_router(mcp_server_router)
router.include_router(mcp_stdio_server_router)
router.include_router(mcp_user_config_router)
router.include_router(message_router)
router.include_router(tool_router)
router.include_router(upload_router)
router.include_router(usage_stats_router)
router.include_router(user_router)
router.include_router(wechat_router)
router.include_router(workspace_router)
router.include_router(stock_router)
