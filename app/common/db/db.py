from motor.motor_asyncio import AsyncIOMotorClient
from ..config import settings

client: AsyncIOMotorClient | None = None
db = None

def init_db():
    global client, db
    print(">>> init_db() CALLED")  # add this
    print(">>> init_db() CALLED")  # add this
    print(">>> init_db() CALLED")  # add this
    print(">>> init_db() CALLED")  # add this

    if client is None:
        client = AsyncIOMotorClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]
    return db



