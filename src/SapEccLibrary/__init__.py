"""SapEccLibrary — bibliothèque SAP GUI (backend ECC/S4) robuste pour Robot Framework.

L'import du nom du paquet comme bibliothèque Robot fonctionne car le nom de la classe
correspond au module :  ``Library    SapEccLibrary``.
"""
from .SapEccLibrary import SapEccLibrary

__version__ = "0.6.4"
__all__ = ["SapEccLibrary"]
