from sqlalchemy import create_engine

# Database URL for SQLite (you can change this to your preferred database)
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=True)