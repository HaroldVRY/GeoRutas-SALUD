from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    frontend_origin: str = "http://localhost:5173"
    database_path: str = "data/app.db"

    class Config:
        env_file = ".env"


settings = Settings()
