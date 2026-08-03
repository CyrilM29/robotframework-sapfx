"""Vocabulaire métier SAP — logique pure, partagée ECC↔Fiori.

Concept issu de l'analyse de playwright-praman (Apache-2.0 — attribution dans
``NOTICE``), réimplémenté sur notre modèle : un **terme métier** (anglais ou
français, synonymes compris — « vendor », « fournisseur », « supplier ») se
résout vers sa fiche — nom canonique, **champ ABAP**, table de référence,
domaine (module SAP) — exploitable par les agents (sap-planner qui parle
métier, sap-generator qui remplit des écrans de sélection SE16) comme par un
humain qui écrit une suite.

Contrat, aligné sur ``sapfx_common.semantic`` : la résolution retourne TOUS
les candidats scorés (:func:`resolve_term`) et le raccourci :func:`lookup_term`
tranche selon un **seuil de refus** — score insuffisant ou ambiguïté (deux
candidats confondables) = erreur **avec la liste des candidats**, jamais de
premier-match silencieux.

Barème (du plus sûr au plus flou) : canonique exact 1.0 · synonyme exact 0.9 ·
champ ABAP exact 0.9 · préfixe 0.7 · flou (SequenceMatcher) ≤ 0.6. Le seuil
par défaut (0.8) n'accepte donc que l'exact ; baisser ``threshold`` assume le
flou en connaissance de cause.

Le vocabulaire livré couvre les champs SAP archi-connus des modules MM/SD/FI
et le modèle de démonstration Flight (SCARR/SPFLI/SFLIGHT — nos suites A4H).
Un site l'étend en passant sa propre liste ``extra`` (termes locaux, Z-champs)
sans toucher au module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class BusinessTerm:
    """Une fiche de vocabulaire : terme canonique → champ ABAP."""
    canonical: str
    abap_field: str
    domain: str
    table: str = ""
    synonyms: tuple = field(default=())
    description: str = ""


@dataclass(frozen=True)
class TermMatch:
    """Un candidat scoré : la fiche, le score, et par quoi il a matché."""
    term: BusinessTerm
    score: float
    matched_via: str


# Champs SAP standard notoires (documentation publique SAP) + modèle Flight.
DEFAULT_VOCABULARY: tuple = (
    # --- MM (achats / articles) ------------------------------------------------
    BusinessTerm("vendor", "LIFNR", "MM", "LFA1",
                 ("supplier", "fournisseur", "creancier", "créancier"),
                 "Vendor / supplier master number"),
    BusinessTerm("material", "MATNR", "MM", "MARA",
                 ("article", "produit", "product"),
                 "Material master number"),
    BusinessTerm("purchase order", "EBELN", "MM", "EKKO",
                 ("po", "commande d'achat", "commande achat", "bon de commande"),
                 "Purchasing document number"),
    BusinessTerm("plant", "WERKS", "MM", "T001W",
                 ("division", "site", "usine"),
                 "Plant"),
    BusinessTerm("purchasing organization", "EKORG", "MM", "T024E",
                 ("organisation d'achats", "org. achats"),
                 "Purchasing organization"),
    BusinessTerm("storage location", "LGORT", "MM", "T001L",
                 ("magasin", "emplacement de stockage"),
                 "Storage location"),
    # --- SD (ventes) -------------------------------------------------------------
    BusinessTerm("customer", "KUNNR", "SD", "KNA1",
                 ("client", "débiteur", "debiteur"),
                 "Customer master number"),
    BusinessTerm("sales order", "VBELN", "SD", "VBAK",
                 ("commande client", "commande de vente", "ordre de vente"),
                 "Sales document number"),
    BusinessTerm("sales organization", "VKORG", "SD", "TVKO",
                 ("organisation commerciale", "org. commerciale"),
                 "Sales organization"),
    BusinessTerm("delivery", "VBELN", "SD", "LIKP",
                 ("livraison", "bon de livraison"),
                 "Outbound delivery number"),
    # --- FI (comptabilité) -------------------------------------------------------
    BusinessTerm("company code", "BUKRS", "FI", "T001",
                 ("société", "societe", "code société"),
                 "Company code"),
    BusinessTerm("accounting document", "BELNR", "FI", "BKPF",
                 ("invoice", "facture", "pièce comptable", "piece comptable"),
                 "Accounting document number"),
    BusinessTerm("fiscal year", "GJAHR", "FI", "BKPF",
                 ("exercice", "exercice comptable", "année fiscale"),
                 "Fiscal year"),
    BusinessTerm("gl account", "SAKNR", "FI", "SKA1",
                 ("compte général", "compte general", "general ledger account"),
                 "G/L account number"),
    # --- Modèle Flight (données de démo A4H — nos suites SE16) -------------------
    BusinessTerm("airline", "CARRID", "FLIGHT", "SCARR",
                 ("compagnie aérienne", "compagnie aerienne", "transporteur",
                  "carrier"),
                 "Airline carrier id"),
    BusinessTerm("connection", "CONNID", "FLIGHT", "SPFLI",
                 ("liaison", "numéro de liaison", "numero de liaison"),
                 "Flight connection number"),
    BusinessTerm("flight date", "FLDATE", "FLIGHT", "SFLIGHT",
                 ("date de vol",),
                 "Flight date"),
)

# Barème praman adapté : exact > synonyme/champ > préfixe > flou.
_SCORE_CANONICAL = 1.0
_SCORE_SYNONYM = 0.9
_SCORE_FIELD = 0.9
_SCORE_PREFIX = 0.7
_SCORE_FUZZY_CAP = 0.6
DEFAULT_THRESHOLD = 0.8
# Deux candidats au-dessus du seuil et à moins de cet écart = confondables.
_AMBIGUITY_GAP = 0.05


def _norm(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def _score_against(term: BusinessTerm, query: str) -> Optional[TermMatch]:
    """Meilleur score de ``query`` contre UNE fiche (ou ``None`` si nul)."""
    if query == _norm(term.canonical):
        return TermMatch(term, _SCORE_CANONICAL, "canonical")
    for synonym in term.synonyms:
        if query == _norm(synonym):
            return TermMatch(term, _SCORE_SYNONYM, "synonym:%s" % synonym)
    if query == _norm(term.abap_field):
        return TermMatch(term, _SCORE_FIELD, "abap_field")
    candidates = [term.canonical, *term.synonyms]
    for name in candidates:
        if _norm(name).startswith(query) and len(query) >= 3:
            return TermMatch(term, _SCORE_PREFIX, "prefix:%s" % name)
    best_ratio, best_name = 0.0, ""
    for name in candidates:
        ratio = SequenceMatcher(None, query, _norm(name)).ratio()
        if ratio > best_ratio:
            best_ratio, best_name = ratio, name
    if best_ratio >= 0.6:
        return TermMatch(term, round(best_ratio * _SCORE_FUZZY_CAP, 3),
                         "fuzzy:%s" % best_name)
    return None


def resolve_term(term: str,
                 vocabulary: Optional[Iterable[BusinessTerm]] = None,
                 extra: Optional[Iterable[BusinessTerm]] = None,
                 domain: Optional[str] = None) -> list:
    """Tous les candidats scorés pour ``term``, du meilleur au moins bon.

    ``vocabulary`` remplace le vocabulaire livré ; ``extra`` l'étend (termes
    site/Z-champs) ; ``domain`` restreint au module (``MM``/``SD``/``FI``/…).
    Ne tranche jamais : l'ambiguïté appartient à l'appelant (:func:`lookup_term`)."""
    entries: list = list(DEFAULT_VOCABULARY if vocabulary is None else vocabulary)
    if extra is not None:
        entries.extend(extra)
    if domain:
        wanted = _norm(domain)
        entries = [entry for entry in entries if _norm(entry.domain) == wanted]
    query = _norm(term)
    if not query:
        return []
    matches = [m for m in (_score_against(entry, query) for entry in entries)
               if m is not None]
    matches.sort(key=lambda m: (-m.score, m.term.canonical))
    return matches


def format_candidates(matches: Sequence[TermMatch], limit: int = 5) -> str:
    """Les candidats en une ligne lisible (pour les messages d'erreur)."""
    return " ; ".join(
        "%s (%s.%s, %s, %d%%)" % (m.term.canonical, m.term.table or "?",
                                  m.term.abap_field, m.term.domain,
                                  round(m.score * 100))
        for m in matches[:limit])


def lookup_term(term: str,
                vocabulary: Optional[Iterable[BusinessTerm]] = None,
                extra: Optional[Iterable[BusinessTerm]] = None,
                domain: Optional[str] = None,
                threshold: float = DEFAULT_THRESHOLD) -> TermMatch:
    """LE candidat pour ``term`` — ou ``ValueError`` actionnable.

    Échoue (avec les candidats) si aucun score n'atteint ``threshold`` ou si
    deux candidats confondables le dépassent (fiches différentes à moins de
    5 points l'un de l'autre) : jamais de premier-match silencieux."""
    matches = resolve_term(term, vocabulary=vocabulary, extra=extra, domain=domain)
    if not matches or matches[0].score < threshold:
        raise ValueError(
            "Terme métier « %s » non résolu (seuil %d%%)%s. Candidats : %s"
            % (term, round(threshold * 100),
               " dans le domaine %s" % domain if domain else "",
               format_candidates(matches) or "aucun"))
    top = matches[0]
    rivals = [m for m in matches[1:]
              if m.score >= threshold and m.score >= top.score - _AMBIGUITY_GAP
              and (m.term.canonical, m.term.domain)
              != (top.term.canonical, top.term.domain)]
    if rivals:
        raise ValueError(
            "Terme métier « %s » ambigu : %s. Préciser domain= ou employer le "
            "terme canonique." % (term, format_candidates([top, *rivals])))
    return top


def lookup_as_dict(term: str, domain: Optional[str] = None,
                   threshold: float = DEFAULT_THRESHOLD) -> dict:
    """:func:`lookup_term` sous forme de dict JSON-safe (keywords, rf-mcp)."""
    match = lookup_term(term, domain=domain, threshold=threshold)
    return {
        "canonical": match.term.canonical,
        "abap_field": match.term.abap_field,
        "table": match.term.table,
        "domain": match.term.domain,
        "synonyms": list(match.term.synonyms),
        "description": match.term.description,
        "score": match.score,
        "matched_via": match.matched_via,
    }
