"""Configuración de la aplicación (variables de entorno o archivo .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FPA_", extra="ignore")

    # Base de datos: SQLite para desarrollo y pruebas.
    # Para pasar a otro motor (p. ej. PostgreSQL) se cambia solo esta variable;
    # ver docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md
    database_url: str = "sqlite:///./fpa_dev.db"

    # Orígenes del frontend permitidos (CORS)
    cors_origins: list[str] = ["http://localhost:5180", "http://127.0.0.1:5180"]

    # "desarrollo" habilita la identidad de desarrollo (cabecera X-Usuario-Dev).
    # Por defecto es "produccion": nadie se autentica hasta configurar OIDC (seguro por defecto).
    entorno: str = "produccion"

    # Archivos subidos: se guardan fuera de cualquier carpeta pública (storage/ no se versiona).
    storage_dir: str = "./storage"
    carga_max_bytes: int = 25 * 1024 * 1024
    # Límites anti zip-bomb (los Excel reales: razón ≈ 35, 9.5 MB, 351 entradas)
    zip_max_entradas: int = 2000
    zip_max_descomprimido: int = 200 * 1024 * 1024
    zip_max_razon: int = 100

    app_nombre: str = "Plataforma FP&A Hotelera"
    app_version: str = "0.1.0"


settings = Settings()
