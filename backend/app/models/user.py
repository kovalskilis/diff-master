from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from database import Base



import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"
    __table_args__ = {'extend_existing': True}

