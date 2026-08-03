"""Déballage minimal des secrets Robot Framework aux frontières externes."""
from typing import Any

from robot.api.types import Secret


def reveal_secret(value: Any) -> Any:
    """Retourne la valeur encapsulée, ou la valeur d'origine si elle est publique."""
    return value.value if isinstance(value, Secret) else value

