import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:////app/instance/home.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    HOME_ROOT = os.getenv("NEXUSYS_HOME_ROOT", "/app/storage")
    KIOSK_ADMIN_PASSWORD = os.getenv("KIOSK_ADMIN_PASSWORD", "rodic123")
