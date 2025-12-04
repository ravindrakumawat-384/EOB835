
from motor.motor_asyncio import AsyncIOMotorClient
from ..config import settings
from ...utils.logger import get_logger

logger = get_logger(__name__)


client: AsyncIOMotorClient | None = None
db = None

def init_db():
    global client, db
    try:
        logger.info("init_db() CALLED")
        if client is None:
            client = AsyncIOMotorClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
        logger.info("MongoDB client initialized successfully.")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB client: {e}")
        raise



