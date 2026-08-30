"""Disponibilité du canal RFC et classification de ses refus (logique pure).

Deux besoins que le canal RFC a et que les deux autres canaux n'ont pas :

* **Savoir s'il est là.** Le RFC est optionnel dans ce dépôt (`pyrfc` n'a
  aucune roue précompilée au-delà de Python 3.12, et toutes ses versions PyPI
  sont ``yanked`` depuis l'archivage du projet par SAP). Une suite RFC doit
  donc pouvoir se SAUTER proprement là où le canal n'existe pas, au lieu de
  rougir là où rien n'est cassé. Encore faut-il distinguer les deux causes
  d'indisponibilité, qui n'ont pas le même remède : le binding Python absent,
  ou le runtime natif NW RFC absent (``sapnwrfc.dll``).
* **Classer ses refus par code technique.** Un échec RFC porte un code stable
  (``TABLE_NOT_AVAILABLE``, ``RFC_LOGON_FAILURE``…) et un texte, lui, localisé
  ou verbeux. La convention n°3 impose de juger sur le code : ce module
  l'extrait, et laisse le texte au seul lecteur.

Le pilotage (import réel, appels) vit dans ``SapApiLibrary`` : ici, rien
n'importe `pyrfc` ni ne touche au réseau.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

#: La marche à suivre, nommée une seule fois : les deux causes d'absence du
#: canal y renvoient, avec leur remède propre.
PYTHON_FLOOR = "3.10 à 3.12"

MODULE_REMEDIATION = (
    "Installer le binding : pip install pyrfc==3.3.1 dans un interpréteur %s "
    "(au-delà, aucune roue précompilée n'existe et toutes les versions PyPI "
    "sont yanked, donc la version s'épingle). Le choix d'interpréteur se fait "
    "à la création du venv, jamais après." % PYTHON_FLOOR)

RUNTIME_REMEDIATION = (
    "Le binding est installé mais le runtime natif NW RFC est introuvable : "
    "provisionner sapnwrfc.dll et les icu*50 (packaging/install-rfc.ps1). Sur "
    "un poste porteur de SAP GUI for Windows 8.00, le composant « SAP NWRFC "
    "x64 Shared » les a souvent déjà déposés dans System32 : "
    "install-rfc.ps1 -CheckOnly le dit.")

GENERIC_REMEDIATION = (
    "Import de pyrfc en échec pour une autre raison : lire le détail ci-dessus, "
    "puis packaging/install-rfc.ps1 -CheckOnly pour diagnostiquer le poste.")


def classify_import_failure(error: BaseException) -> dict[str, Any]:
    """Classe l'échec d'import de `pyrfc` et nomme SON remède.

    Trois cas distingués, parce qu'ils s'attrapent différemment :
    ``module_absent`` (le binding n'est pas installé), ``runtime_absent``
    (le binding est là, la bibliothèque native ne l'est pas : le cas
    « DLL load failed » de Windows) et ``import_failed`` (le reste, rendu
    tel quel plutôt que rangé de force dans une case)."""
    detail = str(error) or type(error).__name__
    lowered = detail.lower()
    if isinstance(error, ModuleNotFoundError) and (
            getattr(error, "name", None) in (None, "pyrfc")):
        return {"reason": "module_absent", "detail": detail,
                "remediation": MODULE_REMEDIATION}
    if "dll load failed" in lowered or "sapnwrfc" in lowered or (
            "shared object" in lowered or "cannot open shared object file" in lowered):
        return {"reason": "runtime_absent", "detail": detail,
                "remediation": RUNTIME_REMEDIATION}
    return {"reason": "import_failed", "detail": detail,
            "remediation": GENERIC_REMEDIATION}


def unavailable_status(error: BaseException) -> dict[str, Any]:
    """État JSON-safe d'un canal RFC indisponible (cause + remède nommés)."""
    status = {"available": False, "version": ""}
    status.update(classify_import_failure(error))
    return status


def available_status(version: Optional[str] = None) -> dict[str, Any]:
    """État JSON-safe d'un canal RFC disponible."""
    return {"available": True, "reason": "ok", "version": str(version or ""),
            "detail": "pyrfc importable", "remediation": ""}


def binding_status(module: Any) -> dict[str, Any]:
    """État du canal à partir du module `pyrfc` DÉJÀ importé : un import qui
    réussit ne suffit pas.

    Mesuré à la première exécution CI du préflight ``runtime_absent``
    (2026-08-29) : le ``__init__`` de pyrfc 3.3.1 AVALE l'échec de chargement
    du runtime natif (``except Exception as ex: print(ex)``), donc sur un
    poste sans ``sapnwrfc.dll`` l'import RÉUSSIT et rend un module sans
    ``Connection``. Faire confiance à l'import déclarait le canal disponible
    exactement là où il ne l'est pas : la suite RFC rougissait au lieu de se
    sauter, et `Open Rfc Connection` sortait en ``AttributeError`` nu. Le
    verdict se lit donc sur le CONTENU du module, et ce cas est classé
    ``runtime_absent`` (même remède, seule la preuve change)."""
    if getattr(module, "Connection", None) is None:
        return {"available": False, "reason": "runtime_absent",
                "detail": ("pyrfc s'importe mais ne porte pas Connection : "
                           "son __init__ avale l'échec de chargement du "
                           "runtime natif NW RFC (il l'imprime sans le "
                           "relever) et rend un module vide."),
                "remediation": RUNTIME_REMEDIATION}
    return available_status(getattr(module, "__version__", ""))


def plain_rfc_value(value: Any) -> Any:
    """Ramène une valeur venue de Robot Framework à un type NU, pour la
    frontière `pyrfc`.

    Motif mesuré (2026-08-27, campagne RFC live) : `pyrfc` contrôle le type
    d'un paramètre de structure par son type EXACT, et refuse une sous-classe
    de ``dict``. Or tout dictionnaire construit dans une suite Robot est un
    ``DotDict``, sous-classe de ``dict`` : sans cette normalisation, AUCUNE
    suite ne peut passer de structure à un module fonction, l'erreur étant un
    ``TypeError`` qui désigne le paramètre sans dire ce qui cloche
    (« dictionary required for structure parameter, received DotDict »).

    La conversion est récursive (structures imbriquées, tables de structures)
    et **ne touche à aucune valeur scalaire** : convertir « au passage » une
    chaîne qui ressemble à un nombre corromprait les champs caractère
    numériques du dictionnaire ABAP, où ``'0400'`` est un numéro de liaison et
    non l'entier 400."""
    if isinstance(value, Mapping):
        return {str(key): plain_rfc_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain_rfc_value(item) for item in value]
    return value


def plain_rfc_parameters(params: Mapping[str, Any]) -> dict[str, Any]:
    """Les paramètres d'un appel RFC, ramenés à des types nus par
    `plain_rfc_value`."""
    return {str(name): plain_rfc_value(value) for name, value in params.items()}


def rfc_error_code(error: BaseException) -> str:
    """Le **code technique** d'un refus RFC, ou la chaîne vide s'il n'en porte
    pas. Les exceptions `pyrfc` exposent ce code dans leur attribut ``key``
    (``TABLE_NOT_AVAILABLE``, ``RFC_LOGON_FAILURE``, ``FU_NOT_FOUND``…), stable
    d'un système et d'une langue à l'autre, contrairement au message."""
    key = getattr(error, "key", "")
    return str(key).strip() if key else ""


def rfc_message_identity(error: BaseException) -> dict[str, str]:
    """L'**identifiant de message** d'un refus applicatif RFC : classe de
    message, type et numéro, plus leur forme compacte ``CLASSE/TYPE/NUMÉRO``.

    C'est le complément FIN du code technique, et il reste conforme à la
    convention n°3 : rien de localisé n'y entre. Le code est stable mais
    grossier (deux causes très différentes le partagent, ainsi
    ``TABLE_WITHOUT_DATA`` sur une table pleine dont un champ est mal
    orthographié) ; l'identifiant, lui, désigne le message ABAP exact et se
    lit sans traduction. Mesuré live (ABAP Platform 2023, 2026-08-28) :
    ``DA/E/131`` pour une table absente, ``AD/E/718`` pour un champ absent,
    ``FL/E/046`` pour un module fonction absent.

    Les exceptions applicatives `pyrfc` portent ces trois valeurs dans
    ``msg_class``/``msg_type``/``msg_number`` ; un refus qui n'en porte pas
    (refus du runtime client, garde de la bibliothèque) rend des chaînes
    vides plutôt qu'un identifiant inventé, et ``message_id`` reste vide tant
    que les trois valeurs ne sont pas là."""
    parts = {name: str(getattr(error, attribute, "") or "").strip()
             for name, attribute in (("message_class", "msg_class"),
                                     ("message_type", "msg_type"),
                                     ("message_number", "msg_number"))}
    complete = all(parts.values())
    parts["message_id"] = "%s/%s/%s" % (
        parts["message_class"], parts["message_type"],
        parts["message_number"]) if complete else ""
    return parts


def describe_rfc_error(error: BaseException) -> dict[str, Any]:
    """Fiche JSON-safe d'un refus RFC : classe pyrfc, code technique, code
    numérique, **identifiant de message** (`rfc_message_identity`) et message.
    Le message est joint pour le seul lecteur : aucune assertion ne doit s'y
    appuyer (convention n°3)."""
    message = getattr(error, "message", None)
    described: dict[str, Any] = {
        "class": type(error).__name__,
        "code": rfc_error_code(error),
        "numeric_code": getattr(error, "code", None),
        "message": str(message if message else error),
    }
    described.update(rfc_message_identity(error))
    return described


def format_message_id_mismatch(subject: str, expected: str,
                               error: BaseException) -> str:
    """Message d'échec quand un refus porte un AUTRE identifiant de message que
    celui attendu (ou n'en porte aucun) : les deux identifiants, le code
    technique pour situer la classe du refus, et le texte en dernier."""
    described = describe_rfc_error(error)
    observed = described["message_id"] or "(aucun identifiant de message)"
    return ("%s a bien échoué, mais pas avec l'identifiant de message attendu : "
            "attendu %s, observé %s (code technique %s). Message du serveur, "
            "pour information seulement : %s"
            % (subject, expected, observed,
               described["code"] or "(aucun)", described["message"]))


def format_code_mismatch(subject: str, expected: str,
                         error: BaseException) -> str:
    """Message d'échec quand un refus survient avec un AUTRE code que celui
    attendu : les deux codes, la classe, et le texte en dernier."""
    described = describe_rfc_error(error)
    observed = described["code"] or "(aucun code technique)"
    return ("%s a bien échoué, mais pas avec le code attendu : attendu %s, "
            "observé %s (%s). Message du serveur, pour information seulement : "
            "%s" % (subject, expected, observed, described["class"],
                    described["message"]))


def format_missing_failure(subject: str, expected: str) -> str:
    """Message d'échec quand l'appel a RÉUSSI là où un refus était attendu.
    Le cas mérite son propre message : un oracle de refus qui passe parce que
    rien n'a échoué ne prouve rien."""
    return ("%s devait échouer avec le code technique %s, mais l'appel a "
            "réussi. Le refus attendu ne se produit plus : la cible a changé, "
            "ou la sonde ne provoque plus le cas visé."
            % (subject, expected))
