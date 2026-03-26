from app.core.config import MONGODB_NAME, MONGODB_URL
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.User import Users
from app.models.Tenants import Tenants
from app.models.Membership import Membership

logger = logging.getLogger(__name__)

client = None

async def startup_db():
    global client
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        await init_beanie(
            database= client[MONGODB_NAME],
            document_models= [
                Users,
                Tenants,
                Membership
            ]
        )
        logger.info("MongoDB connection successfull")
    except Exception as e:
        logger.error("An error occured while connecting to MongoDB")
        logger.error(f"Error: {str(e)}")
        raise e
        
async def close_connection():
    global client
    try:
        if client:
            client.close()
            logger.info("MongoDB connection closed successfully")
    except Exception as e:
        logger.error("An error occurred while closing MongoDB connection")
        logger.error(f"Error: {str(e)}")