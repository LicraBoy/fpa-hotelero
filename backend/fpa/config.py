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

    # Sesiones y contraseñas de los usuarios locales (ADR 0005)
    cookie_nombre: str = "fpa_sesion"
    # `Secure`: el navegador solo la envía por HTTPS (y por http://localhost). Sin HTTPS en la red
    # interna, poner FPA_COOKIE_SEGURA=false (menos seguro: TI debe saberlo).
    cookie_segura: bool = True
    sesion_inactividad_min: int = 480  # cierra la sesión tras 8 h sin usar
    sesion_maxima_h: int = 12  # y, pase lo que pase, a las 12 h
    login_max_intentos: int = 5  # intentos fallidos seguidos antes de bloquear la cuenta
    login_bloqueo_min: int = 15
    password_min_largo: int = 10
    # Roles que deben tener TOTP activo (se avisa al entrar) `[POR VALIDAR con Contraloría/TI]`
    mfa_roles_obligatorios: list[str] = []

    # Archivos subidos: se guardan fuera de cualquier carpeta pública (storage/ no se versiona).
    storage_dir: str = "./storage"
    carga_max_bytes: int = 25 * 1024 * 1024
    adjunto_max_bytes: int = 10 * 1024 * 1024  # evidencia de un comentario
    adjuntos_max_por_comentario: int = 5
    # Límites anti zip-bomb (los Excel reales: razón ≈ 35, 9.5 MB, 351 entradas)
    zip_max_entradas: int = 2000
    zip_max_descomprimido: int = 200 * 1024 * 1024
    zip_max_razon: int = 100

    # Caché en memoria de los reportes (un proceso). 0 = apagada. Ver servicios/cache_reportes.py
    cache_reportes_ttl_s: float = 300.0
    cache_reportes_max: int = 128

    app_nombre: str = "Plataforma FP&A Hotelera"
    app_version: str = "0.1.0"


settings = Settings()
