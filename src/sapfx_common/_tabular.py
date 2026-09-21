"""Socle commun des rendus tabulaires (SVG, XLSX), logique pure et privée.

Ce module n'est pas une surface de keywords : il porte ce que deux formats de
sortie doivent décider EXACTEMENT pareil, faute de quoi le même relevé rendu
deux fois n'aurait pas les mêmes colonnes ni les mêmes coupes. Les façades
publiques sont :mod:`sapfx_common.table_svg` et
:mod:`sapfx_common.table_xlsx`, qui re-exportent ce qu'un appelant Robot doit
atteindre.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence  # noqa: F401

__all__ = ["table_columns", "cell_text", "normalize_rows", "xml_escape",
           "header_labels", "blank_rows", "row_limit", "unique_header"]


def row_limit(value: Any) -> Optional[int]:
    """Le plafond de lignes, refusé s'il est négatif.

    Les cinq formats partagent cette lecture : sans elle, un même argument
    recevait trois interprétations (borne ignorée ici, zéro ligne écrite là),
    et le format qu'on ne relit pas rendait un verdict décrivant un fichier
    qui n'existait pas. Un plafond négatif n'a aucun sens : le dire vaut
    mieux que le deviner.
    """
    from sapfx_common.robot_args import as_optional_int

    borne = as_optional_int(value, "max_rows")
    if borne is not None and borne < 0:
        raise ValueError(
            "max_rows ne peut pas être négatif (reçu %s). Passer None pour "
            "tout rendre, ou un entier positif pour borner." % borne)
    return borne


def unique_header(labels: Sequence[str], source: str) -> None:
    """Refuse un en-tête où deux colonnes portent le même libellé.

    Employé à la RELECTURE : un fichier dont l'en-tête répète un libellé ne
    peut pas être relu fidèlement, la seconde colonne écrasant la première
    dans le dictionnaire rendu. Le piège est qu'écriture et relecture perdent
    alors la même colonne, de sorte qu'un aller-retour reste vert et qu'une
    colonne sort du périmètre PROUVÉ sans que rien ne le dise.
    """
    vus: dict[str, int] = {}
    for index, libelle in enumerate(labels):
        if libelle in vus:
            raise ValueError(
                "%s : les colonnes %d et %d portent le même en-tête %r, donc "
                "le fichier ne peut pas être relu fidèlement (l'une écraserait "
                "l'autre). Réécrire le fichier sans `headers`, ou avec des "
                "libellés distincts." % (source, vus[libelle] + 1, index + 1,
                                         libelle))
        vus[libelle] = index


def blank_rows(rows: Iterable[Mapping[str, Any]],
               columns: Optional[Sequence[str]] = None) -> int:
    """Combien de lignes d'un relevé sont ENTIÈREMENT vides.

    Le témoin qu'un compte de lignes ne donne pas, et il a un coût réel : une
    grille ALV ne matérialise ses lignes qu'au fil du défilement, et une
    lecture faite sur des lignes non chargées rend des cellules VIDES au lieu
    de lever. Le relevé a alors le bon nombre de lignes, il se relit
    fidèlement, il se compare à lui-même sans écart, et il est vide.

    Mesuré le 2026-09-15 : la même lecture du rapport RSPARAM rendait 1635
    lignes pleines sur un système du banc et 1639 lignes dont 137 remplies sur
    l'autre. L'écart est établi, sa cause ne l'est pas (la matérialisation
    dépend de la fenêtre visible autant que du système) ; ce qui l'est, c'est
    qu'aucune garde fondée sur le NOMBRE ne pouvait le voir.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    return sum(1 for ligne in lignes
               if not any(str(ligne.get(colonne) or "").strip()
                          for colonne in colonnes))


def header_labels(columns: Sequence[str],
                  headers: Optional[Mapping[str, Any]] = None,
                  require_unique: bool = False) -> list[str]:
    """Les libellés d'en-tête, dans l'ordre des colonnes.

    ``headers`` est la carte ``{id technique: libellé affiché}`` que rend
    `Get Grid Column Titles` : elle fait qu'un fichier livré porte les noms que
    SAP montre à l'écran, au lieu d'identifiants que seul le développeur
    reconnaît. Une colonne absente de la carte garde son id, et un libellé vide
    aussi : mieux vaut un nom technique qu'une colonne sans nom.

    ``require_unique`` sert les formats dont l'en-tête devient une CLÉ (JSON,
    Parquet) : deux colonnes au même libellé y écraseraient l'une l'autre, et
    une colonne disparaîtrait d'un fichier qui aurait pourtant l'air complet.
    Le cas est réel, une ALV pouvant afficher deux colonnes homonymes. Les
    formats positionnels (SVG, CSV, XLSX) restent tolérants : ils rendent alors
    l'écran tel qu'il est, doublon compris.
    """
    if not headers:
        return [str(colonne) for colonne in columns]
    libelles = []
    for colonne in columns:
        brut = headers.get(str(colonne))
        texte = "" if brut is None else str(brut).strip()
        libelles.append(texte or str(colonne))
    if require_unique:
        vus: dict[str, str] = {}
        for colonne, libelle in zip(columns, libelles, strict=True):
            if libelle in vus:
                raise ValueError(
                    "Les colonnes %s et %s portent le même libellé %r : dans "
                    "ce format l'en-tête est une CLÉ, donc l'une écraserait "
                    "l'autre et disparaîtrait d'un fichier d'apparence "
                    "complète. Retirer `headers` pour garder les identifiants "
                    "techniques." % (vus[libelle], colonne, libelle))
            vus[libelle] = str(colonne)
    return libelles


def xml_escape(text: Any) -> str:
    """Échappe une valeur pour du contenu XML (SVG comme XLSX, tous deux XML).

    ``&`` en premier, sans quoi les entités produites par les remplacements
    suivants seraient ré-échappées. Les caractères de contrôle sont retirés :
    ils ne sont pas représentables en XML 1.0, et un seul suffit à faire
    rejeter le document entier par un lecteur strict, Excel compris.
    """
    brut = "" if text is None else str(text)
    brut = brut.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    brut = brut.replace('"', "&quot;").replace("'", "&apos;")
    return "".join(c for c in brut if c >= " " or c == "\t")


def normalize_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Copie défensive d'un relevé, en refusant ce qui n'est pas une ligne.

    Un appelant qui passe une liste de chaînes (une colonne au lieu d'un
    relevé, confusion courante quand les deux se ressemblent à l'écran) doit
    l'apprendre ici, et non par un rendu vide parfaitement plausible.
    """
    lignes = []
    for index, ligne in enumerate(rows):
        if not isinstance(ligne, Mapping):
            raise ValueError(
                "Ligne %d : un relevé est une liste de dictionnaires "
                "({colonne: valeur}), reçu %s. Une lecture de grille rend "
                "cette forme ; une liste de valeurs seules n'en est pas une."
                % (index, type(ligne).__name__))
        lignes.append(dict(ligne))
    return lignes


def table_columns(rows: Iterable[Mapping[str, Any]],
                  columns: Optional[Sequence[str]] = None) -> list[str]:
    """Les colonnes à rendre, dans l'ordre.

    Sans ``columns``, l'union ORDONNÉE des clés rencontrées : une ligne plus
    riche que la première n'est donc pas amputée en silence. Avec ``columns``,
    une colonne absente de TOUTES les lignes fait échouer en listant ce qui
    existe, parce qu'un tableau rendu avec une colonne entièrement vide se lit
    comme une donnée manquante côté système, et non comme une faute de frappe
    côté test.

    Exception assumée : sur un relevé VIDE, aucune colonne ne peut être
    confrontée à quoi que ce soit, donc la liste demandée est prise telle
    quelle et le fichier produit ne porte que son en-tête. Refuser reviendrait
    à interdire d'écrire l'en-tête d'un résultat légitimement vide.
    """
    lignes = normalize_rows(rows)
    vues: list[str] = []
    for ligne in lignes:
        for cle in ligne:
            if str(cle) not in vues:
                vues.append(str(cle))
    if columns is None:
        return vues
    voulues = [str(c).strip() for c in columns if str(c).strip()]
    if not voulues:
        raise ValueError(
            "La liste de colonnes est vide : passer None pour rendre toutes "
            "les colonnes du relevé.")
    absentes = [c for c in voulues if c not in vues]
    if absentes and lignes:
        raise ValueError(
            "Colonne(s) absente(s) du relevé : %s. Colonnes disponibles : %s"
            % (", ".join(absentes), ", ".join(vues) or "(aucune)"))
    return voulues


def cell_text(value: Any, max_chars: int = 0) -> tuple[str, bool]:
    """Le texte d'une cellule et un témoin de troncature.

    Les blancs de structure (tabulation, retours) deviennent des espaces : une
    cellule est une ligne unique dans les deux formats visés, et un retour
    laissé tel quel casserait l'alignement du SVG sans rien apporter.
    """
    brut = "" if value is None else str(value)
    brut = brut.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    if max_chars and len(brut) > max_chars:
        return brut[: max(1, int(max_chars) - 1)] + "…", True
    return brut, False
