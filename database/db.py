from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging
from config import DATABASE_URL
from database.models import Base

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
    
    def init_db(self):
        try:
            self.engine = create_engine(
                DATABASE_URL,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                echo=False,
                pool_recycle=3600
            )
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            Base.metadata.create_all(bind=self.engine)
            logger.info("MySQL Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def get_session(self) -> Session:
        if not self.SessionLocal:
            self.init_db()
        return self.SessionLocal()
    
    def close(self):
        if self.engine:
            self.engine.dispose()

db = Database()