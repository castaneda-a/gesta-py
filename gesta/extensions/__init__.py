# =============================================================================
# extensions/__init__.py
# =============================================================================
# Expone las extensiones disponibles de Gesta. Cada extensión adapta la
# librería a un tipo de negocio específico heredando de la clase base Gesta.
#
#   from gesta.extensions import WellnessStudio
# =============================================================================

from gesta.extensions.wellness import WellnessStudio

__all__ = [
    "WellnessStudio",
]