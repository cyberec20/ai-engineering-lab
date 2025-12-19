# crew/config_loader.py

"""
Cargador sencillo de configuración para API keys y otros ajustes.

- Lee crew/config/api_keys.yml
- Mantiene un pequeño caché en memoria para no re-leer el archivo en cada llamada.
- Proporciona get_api_key(provider) para que otros módulos (ej. stock_picker.py)
  obtengan las claves sin acoplarse al formato interno.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import yaml

_CONFIG_CACHE: Dict[str, Any] | None = None


def _default_config_path() -> str:
    """
    Devuelve la ruta por defecto del archivo YAML de API keys:
    crew/config/api_keys.yml
    """
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "config", "api_keys.yml")


def load_config(path: str | None = None) -> Dict[str, Any]:
    """
    Carga el YAML de configuración y lo deja en caché.
    Si el archivo no existe o está vacío, devuelve {}.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if path is None:
        path = _default_config_path()

    cfg: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    cfg = data
        except Exception as exc:
            # En caso de error, dejamos cfg vacío pero no rompemos la app.
            print(f"[config_loader] Error al leer {path}: {exc}")

    _CONFIG_CACHE = cfg
    return cfg


def get_api_key(provider: str, env_var: str | None = None) -> str | None:
    """
    Devuelve la API key para un proveedor dado.

    Orden de prioridad:
    1) YAML: sección provider.api_key
    2) Variable de entorno env_var (si se proporciona)
    3) None si no se encuentra nada
    """
    cfg = load_config()
    section = cfg.get(provider, {})
    if isinstance(section, dict):
        key = section.get("api_key")
        if isinstance(key, str) and key.strip():
            return key.strip()

    if env_var:
        val = os.getenv(env_var)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None
