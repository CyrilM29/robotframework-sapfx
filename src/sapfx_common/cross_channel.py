"""Croisement DDIC et OData : périmètre, rapprochement, artefact, comparaison.

Logique **pure** (aucune E/S, aucun COM, aucun HTTP) de la campagne « quelles
tables et quels entity sets sont réellement disponibles sur la cible, et
disent-ils la même chose » (plan ``specs/croisement-ddic-odata-ecc-s4hana.md``).
Le module est modelé sur ``ddic_inventory`` : périmètre borné et validé,
assemblage d'un artefact JSON trié, empreinte hors horodatage, comparaison de
deux cibles à périmètre équivalent, rapport Markdown.

Il est **importé comme bibliothèque Robot** (``Library
sapfx_common.cross_channel``) par la couche ``resources/`` : chaque fonction
publique listée dans ``__all__`` devient un keyword. D'où deux contraintes de
forme assumées ici : uniquement des fonctions de module (jamais de classe ni de
dataclass en argument) et des signatures JSON-safe.

Trois enseignements live (A4H, 2026-08-22) sont encodés dans le code plutôt que
dans un commentaire :

- **la correspondance entity set / table ne se devine pas**. ``SNWD_CONTACT``
  existe, est transparente, s'ouvre dans SE16 et contient 0 entrée, quand
  ``ContactSet`` en publie 41 : la vraie table est ``SNWD_BPA_CONTACT``. Aucune
  fonction d'ici ne dérive une table d'un nom d'entity set ; le couple est une
  donnée déclarée que le test prouve ;
- **le rapprochement de champs doit connaître les acronymes**. ``ProductID``
  se normalise en ``PRODUCT_ID`` (15 propriétés appariées sur 21 pour
  ``ProductSet``), là où une coupure devant chaque majuscule produit
  ``PRODUCT_I_D`` et perd l'appariement (14 sur 21) ;
- **un renommage métier n'est pas rattrapable mécaniquement**.
  ``BusinessPartnerID`` face à ``BP_ID`` ne se déduit d'aucune règle : c'est
  un alias déclaré, et c'est justement la clé de l'entity type.
"""
from __future__ import annotations

__all__ = [
    "validate_cross_channel_scope",
    "catalog_coverage",
    "normalize_identifier",
    "describe_service_contract",
    "write_simulation_candidates",
    "classify_entity_set_probes",
    "odata_error_code",
    "compare_odata_properties_with_ddic_fields",
    "build_couple_verdict",
    "shortlist_write_candidates",
    "selection_criteria",
    "describe_ddic_table",
    "build_cross_channel_artifact",
    "cross_channel_artifact_json",
    "cross_channel_hash",
    "compare_cross_channel_artifacts",
    "render_cross_channel_report",
]


from ._cross_channel_contract import (  # noqa: F401,E402
    COUPLE_EXPECTATIONS,
    SCHEMA_VERSION,
    catalog_coverage,
    classify_entity_set_probes,
    compare_odata_properties_with_ddic_fields,
    describe_service_contract,
    normalize_identifier,
    odata_error_code,
    validate_cross_channel_scope,
    write_simulation_candidates,
)
from ._cross_channel_artifact import (  # noqa: F401,E402
    build_couple_verdict,
    build_cross_channel_artifact,
    compare_cross_channel_artifacts,
    cross_channel_artifact_json,
    cross_channel_hash,
    describe_ddic_table,
    render_cross_channel_report,
    selection_criteria,
    shortlist_write_candidates,
)
