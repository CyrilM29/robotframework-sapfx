"""Mixin des lectures de **surface d'attaque** par le canal RFC.

Voisin de `_rfc_security.py` plutôt qu'ajouté dedans (convention #13). Ce que
ces keywords ajoutent : `_rfc_security.py` lit la CONFIGURATION de sécurité
(paramètres de profil, comptes livrés, destinations) ; ici on lit ce qui est
réellement ATTEIGNABLE, et les deux ne coïncident pas.

Trois pièges d'appel mesurés le 2026-09-14 sur ABAP Platform 2023 (release
758) sont encodés ici, et tous trois produisent un résultat plausible plutôt
qu'une erreur visible :

1. ``RSAU_READ_LOG`` déclare ``IS_INTV`` OBLIGATOIRE. Appelé sans lui, il rend
   zéro entrée et zéro fichier **sans lever quoi que ce soit**. Graver ce zéro
   revient à écrire « le journal d'audit est vide » sans l'avoir lu. Et la
   structure porte ``DAT_FROM``/``DAT_TO``, pas ``DATE_FROM`` : l'orthographe
   plausible sort en ``RFC_INVALID_PARAMETER`` côté client, donc sans jamais
   atteindre le système.
2. Les services web se lisent dans DEUX tables : ``ICFSERVLOC`` porte le
   drapeau d'activation, ``ICFSERVICE`` porte le nom. Lire la seconde seule
   donne 3410 noeuds dont on ignore lesquels répondent.
3. ``RFCTRUST`` n'a pas de champ ``RFCSYSID`` (ses clés sont ``RFCTRUSTID``,
   ``TLICENSE_NR``, ``RFCTRUSTSY``, ``LLICENSE_NR``). Le demander sort en
   ``TABLE_WITHOUT_DATA``, code qui accuse la TABLE d'être vide : une campagne
   conclurait « aucune relation de confiance » sans avoir rien lu, ce qui est
   d'autant plus traître que la réponse se trouve être la bonne.

Logique pure (classification, verdicts, résumés) dans
``sapfx_common.security_surface``.
"""
from __future__ import annotations

import datetime
from typing import Any, Mapping, Optional

from sapfx_common import robot_args, security_baseline, security_surface

from ._rfc_security import RfcSecurityKeywords

#: Les motifs de nom qui désignent un service web notoirement sensible. Une
#: aide au rapport, jamais un critère d'échec : ce qui est sensible dépend du
#: site, et le keyword rend l'inventaire complet à côté.
SENSITIVE_ICF_PATTERNS = ("webgui", "its", "soap", "bsp", "nwbc", "public",
                          "ui2", "gui", "wsnavigator", "sldcheck", "ping")

#: La fenêtre de lecture du journal d'audit, par défaut. Large à dessein : une
#: fenêtre courte rendrait zéro entrée sur un système peu sollicité, et ce zéro
#: serait lu comme une absence de couverture alors qu'il ne dirait rien.
DEFAULT_AUDIT_WINDOW_DAYS = 365


class RfcSurfaceKeywords(RfcSecurityKeywords):
    """Mixin de :class:`SapApiLibrary` : la surface d'attaque par RFC."""

    # ------------------------------------------------------------------ #
    # Comptes : utilisable n'est pas la même chose que non verrouillé
    # ------------------------------------------------------------------ #
    def read_account_usability(self, alias: str = "default",
                               client: Optional[str] = None,
                               today: Optional[str] = None) -> dict[str, Any]:
        """Lit TOUS les comptes du mandant de connexion et dit lesquels sont
        réellement **utilisables**.

        Rend le résumé de ``security_surface.summarize_accounts`` :
        ``{"total", "usable", "unusable", "by_status", "accounts"}``, chaque
        fiche portant son statut (``active``, ``locked``, ``expired``,
        ``not_yet_valid``, ``unknown``) et ses raisons.

        **Ce que ce keyword mesure et que la lecture du verrouillage ne mesure
        pas.** Sur la cible, les six comptes du mandant sont tous non
        verrouillés, donc `Read Standard Users Status` rapporte « aucun compte
        verrouillé », ce qui est exact. Deux d'entre eux portent une date de
        fin de validité échue depuis vingt mois et ne peuvent plus servir : la
        surface réelle est de quatre comptes, pas six. Les deux lectures
        répondent à deux questions, et seule celle-ci répond à « qui peut
        entrer ».

        ``today`` (``AAAAMMJJ``) est calculé ici et passé à la logique pure,
        qui ne lit jamais l'horloge : c'est ce qui rend le classement
        reproductible en test. Un appelant peut le forcer pour rejouer un
        relevé daté.

        ``client`` ne CHANGE pas le mandant lu (la lecture porte sur celui de
        la connexion) : il est reporté dans le résumé pour qu'un artefact dise
        de quel mandant il parle.
        """
        rows = self.read_rfc_table(
            "USR02", ["BNAME", "UFLAG", "CLASS", "USTYP", "GLTGV", "GLTGB",
                      "TRDAT", "CODVN"], alias=alias)
        today = str(today or datetime.date.today().strftime("%Y%m%d"))
        comptes = []
        for row in rows:
            lock = security_baseline.classify_user_lock(row.get("UFLAG"))
            comptes.append({
                "user": str(row.get("BNAME", "")).strip(),
                "locked": lock["locked"],
                "lock_reasons": lock["reasons"],
                "valid_from": str(row.get("GLTGV", "")).strip(),
                "valid_to": str(row.get("GLTGB", "")).strip(),
                "user_group": str(row.get("CLASS", "")).strip(),
                "user_type": str(row.get("USTYP", "")).strip(),
                "hash_version": str(row.get("CODVN", "")).strip(),
                "last_logon": str(row.get("TRDAT", "")).strip(),
            })
        resume = security_surface.summarize_accounts(comptes, today)
        resume["client"] = client
        resume["as_of"] = today
        resume["hash_versions"] = dict(sorted(
            {v: len([c for c in comptes if c["hash_version"] == v])
             for v in {c["hash_version"] for c in comptes}}.items()))
        return resume

    # ------------------------------------------------------------------ #
    # Exposition web : déclaré n'est pas servi
    # ------------------------------------------------------------------ #
    def read_icf_exposure(self, alias: str = "default",
                          sensitive_patterns: Any = None) -> dict[str, Any]:
        """Lit la **surface d'exposition web** : services déclarés, services
        actifs, et ce que les actifs exposent.

        Rend ``{"declared", "active", "active_without_ssl", "with_stored_user",
        "sensitive_active", "exposure_ratio", "virtual_hosts"}``.

        **Pourquoi deux tables**, et c'est le piège du domaine : le drapeau
        d'activation vit dans ``ICFSERVLOC`` et le nom lisible dans
        ``ICFSERVICE``, jointes par l'identifiant de noeud. Lire la seconde
        seule donne 3410 noeuds sans savoir lesquels répondent ; mesuré sur la
        cible, 219 sont actifs, soit seize fois moins. Rapporter le grand
        chiffre produit une surface que personne ne peut auditer.

        ``with_stored_user`` isole les services qui portent un compte de
        service : ceux-là s'exécutent sans authentifier leur appelant, ce qui
        en fait la propriété la plus intéressante de l'inventaire. Elle ne se
        déduit pas de l'activation et demande la seconde table.

        Le keyword ne juge pas : il RAPPORTE. Ce qui est sensible dépend du
        site, donc ``sensitive_patterns`` n'alimente qu'une liste de rappel à
        côté de l'inventaire complet.
        """
        actifs = self.read_rfc_table("ICFSERVLOC", ["ICF_NAME", "ICFPARGUID",
                                                    "ICFACTIVE", "ICFSRVGRP"],
                                     alias=alias)
        fiches_service = self.read_rfc_table(
            "ICFSERVICE", ["ICF_NAME", "ICFPARGUID", "ORIG_NAME", "ICFALTNME",
                           "ICF_USER", "ICF_MANDT", "SSLFLAG"], alias=alias)
        # Jointure sur la clé COMPLÈTE (noeud + parent) et non sur le seul
        # nom : un même nom est porté par plusieurs noeuds de l'arbre (324 sur
        # la cible, dont 18 aux propriétés différentes), donc indexer sur le
        # nom attribue les propriétés du premier à tous les autres. Mesuré le
        # 2026-09-14 : aucun noeud ACTIF n'est concerné sur cette cible, mais
        # la propriété qui diverge ailleurs est justement celle qui compte ici
        # (le compte de service), et elle dépend du parent.
        par_noeud: dict[tuple[str, str], Mapping[str, Any]] = {}
        for row in fiches_service:
            cle_complete = (str(row.get("ICF_NAME", "")).strip(),
                            str(row.get("ICFPARGUID", "")).strip())
            par_noeud.setdefault(cle_complete, row)

        noeuds = []
        for row in actifs:
            cle = (str(row.get("ICF_NAME", "")).strip(),
                   str(row.get("ICFPARGUID", "")).strip())
            trouvee = par_noeud.get(cle)
            fiche: Mapping[str, Any] = trouvee if trouvee is not None else {}
            nom = cle[0]
            if trouvee is not None:
                nom = (str(fiche.get("ORIG_NAME", "")).strip()
                       or str(fiche.get("ICFALTNME", "")).strip() or cle[0])
            noeuds.append({
                "name": nom,
                "active": str(row.get("ICFACTIVE", "")).strip().upper() == "X",
                "ssl": str(fiche.get("SSLFLAG", "")).strip().upper() == "X",
                "stored_user": str(fiche.get("ICF_USER", "")).strip(),
                "client": str(fiche.get("ICF_MANDT", "")).strip(),
                # Le témoin d'appariement : un noeud dont la fiche descriptive
                # manque reste COMPTÉ (le perdre sous-estimerait la surface,
                # mauvais sens de l'erreur) mais il est distingué, sans quoi
                # une jointure cassée rendrait un résumé de système sain.
                "named": trouvee is not None,
            })

        motifs = sensitive_patterns or SENSITIVE_ICF_PATTERNS
        resume = security_surface.summarize_icf_exposure(noeuds, motifs)
        hotes = self.read_rfc_table("ICFVIRHOST",
                                    ["ICF_NAME", "HOSTNUMBER", "PROTOCOL"],
                                    alias=alias)
        resume["virtual_hosts"] = [
            {"host": str(h.get("ICF_NAME", "")).strip(),
             "number": str(h.get("HOSTNUMBER", "")).strip(),
             "protocol": str(h.get("PROTOCOL", "")).strip()} for h in hotes]
        return resume

    # ------------------------------------------------------------------ #
    # Commandes du système d'exploitation
    # ------------------------------------------------------------------ #
    def read_external_commands(self, alias: str = "default") -> dict[str, Any]:
        """Inventorie les **commandes du système d'exploitation** déclarées
        dans le système, et distingue celles qui acceptent des arguments
        additionnels.

        Rend ``{"total", "accepting_additional", "fixed", "customer_defined",
        "customer_defined_accepting_additional", "by_os"}``.

        **Pourquoi cette distinction porte tout le sens de l'inventaire** :
        une commande dont l'appelant peut compléter les arguments à
        l'exécution ne donne pas la même surface qu'une commande figée. C'est
        l'écart entre « exécuter une sauvegarde » et « exécuter ce que
        l'appelant voudra ». Mesuré sur la cible : 109 des 117 commandes
        déclarées l'acceptent.

        Les commandes définies sur le système (espace de noms client) sont
        isolées parce qu'elles ne viennent d'aucun standard et sont donc ce
        qu'un audit regarde en premier. Sur la cible, il n'y en a aucune : un
        inventaire vide MESURÉ, qui a valeur de résultat.

        Le keyword ne lit aucun secret et n'exécute évidemment rien.
        """
        result = self.call_rfc("SXPG_COMMAND_LIST_GET", alias=alias)
        commandes = result.get("COMMAND_LIST") or []
        return security_surface.summarize_external_commands(commandes)

    # ------------------------------------------------------------------ #
    # Journal d'audit : la configuration CROISÉE avec le contenu
    # ------------------------------------------------------------------ #
    def read_audit_log_coverage(self, alias: str = "default",
                                window_days: Any = DEFAULT_AUDIT_WINDOW_DAYS,
                                today: Optional[str] = None) -> dict[str, Any]:
        """Croise la configuration du journal d'audit et son **contenu réel**,
        et rend le verdict de couverture.

        Rend ``{"verdict", "configuration_verdict", "entries", "files",
        "window_days", "consistent", "note"}``, plus la configuration complète
        sous ``configuration``.

        **Ce que ce keyword prouve et que `Get Audit Configuration` ne peut
        que déduire.** La configuration dit « armé, dix emplacements déclarés,
        aucun actif », d'où l'on conclut que le journal n'enregistre rien.
        C'était un raisonnement ; la lecture du journal sur la fenêtre le rend
        CONSTATÉ. Mesuré sur la cible : zéro entrée et zéro fichier sur un an
        comme sur quatre.

        **Le piège d'appel, et il est silencieux.** ``RSAU_READ_LOG`` déclare
        son intervalle OBLIGATOIRE mais ne le vérifie pas : appelé sans lui, il
        rend zéro entrée sans lever la moindre erreur, et ce zéro passe
        parfaitement pour une mesure. La structure attend par ailleurs
        ``DAT_FROM``/``DAT_TO`` et non ``DATE_FROM``, orthographe qui sort en
        ``RFC_INVALID_PARAMETER`` levé côté client, donc sans jamais atteindre
        le système. Le keyword compose l'intervalle lui-même, pour que
        l'appelant ne puisse commettre ni l'un ni l'autre.

        Une lecture qui ÉCHOUE rend ``not_measured`` et jamais zéro : sur un
        contrôle d'audit, confondre « vide » et « non lu » est le faux positif
        que tout ce domaine cherche à éviter.
        """
        configuration = self.get_audit_configuration(alias=alias)
        try:
            days = int(str(window_days).strip())
        except (TypeError, ValueError):
            raise ValueError(
                f"`window_days` doit être un entier de jours, reçu "
                f"{window_days!r}. Via la frontière MCP tout arrive en chaîne, "
                f"d'où la conversion explicite.") from None

        end = (datetime.datetime.strptime(str(today), "%Y%m%d").date()
               if today else datetime.date.today())
        start = end - datetime.timedelta(days=days)
        entries: Optional[int] = None
        files: Optional[int] = None
        ok = True
        try:
            out = self.call_rfc(
                "RSAU_READ_LOG", alias=alias,
                IS_INTV={"DAT_FROM": start.strftime("%Y%m%d"),
                         "TIM_FROM": "000000",
                         "DAT_TO": end.strftime("%Y%m%d"),
                         "TIM_TO": "235959"})
            # La réponse doit PORTER ses tables de sortie. Sans ce contrôle,
            # une réponse vide ou de forme inattendue (module renommé sur une
            # autre release, refus rendu sans exception) donnerait zéro entrée
            # et « lecture réussie », donc exactement le verdict de silence
            # recherché, obtenu sans avoir rien lu. C'est le piège de l'appel
            # sans intervalle, déplacé d'un cran.
            if not isinstance(out, Mapping) or "ET_DATA" not in out:
                ok = False
            else:
                entries = len(out.get("ET_DATA") or [])
                files = len(out.get("ET_STAT") or [])
        except Exception:  # noqa: BLE001 - un refus n'est pas un journal vide
            ok = False

        verdict = security_surface.corroborate_audit_coverage(
            configuration, entries, files_seen=files, window_days=days,
            read_succeeded=ok)
        verdict["configuration"] = configuration
        return verdict

    # ------------------------------------------------------------------ #
    # Relations de confiance RFC
    # ------------------------------------------------------------------ #
    def read_rfc_trust_surface(self, alias: str = "default") -> dict[str, Any]:
        """Inventorie les **relations de confiance RFC** et la liste blanche
        des rappels.

        Rend ``{"trusted_systems", "trusting_systems",
        "callback_allowlist_entries", "trusted_ids", "trusting_ids",
        "callback_destinations", "any_trust_configured"}``.

        **Pourquoi cet inventaire vaut d'exister même vide**, et il l'est sur
        la cible : sans lui, une campagne ne peut pas distinguer « aucune
        relation de confiance n'est configurée » de « personne n'a regardé ».
        Le jour où une relation apparaît, seule la première situation la rend
        visible. Un inventaire vide mesuré est un résultat ; un inventaire
        jamais lu est un angle mort, et c'est exactement ce qu'était cette
        zone.

        **Le piège de lecture** : ``RFCTRUST`` ne porte PAS de champ
        ``RFCSYSID``, contrairement à sa voisine ``RFCSYSACL``. Le demander
        sort en ``TABLE_WITHOUT_DATA``, code qui accuse la table d'être vide,
        et la conclusion « aucune relation de confiance » se trouve être
        exacte sur cette cible, ce qui rend l'erreur invisible. Les champs
        projetés ici sont ceux du contrat réel, relevé dans le dictionnaire.
        """
        entrants = self.read_rfc_table(
            "RFCTRUST", ["RFCTRUSTSY", "RFCTRUSTID", "RFCDEST"], alias=alias)
        sortants = self.read_rfc_table(
            "RFCSYSACL", ["RFCSYSID", "RFCTRUSTSY", "RFCDEST"], alias=alias)
        rappels = self.read_rfc_table(
            "RFCCBWHITELIST", ["DESTINATION", "CALLED_FM", "CALLED_BACK_FM"],
            alias=alias)
        return security_surface.summarize_trust_surface(
            [{"system": r.get("RFCTRUSTSY")} for r in entrants],
            [{"system": r.get("RFCSYSID")} for r in sortants],
            [{"destination": r.get("DESTINATION")} for r in rappels])

    # ------------------------------------------------------------------ #
    # Autorisations : les porteurs d'objets critiques
    # ------------------------------------------------------------------ #
    def count_authorization_object_usage(self, objects: Any,
                                         alias: str = "default"
                                         ) -> dict[str, int]:
        """Compte, par objet d'autorisation, le nombre de lignes de rôle qui
        le portent.

        Rend ``{objet: nombre}`` dans l'ordre demandé. Ce n'est PAS un compte
        de droits effectifs : c'est la taille de l'empreinte d'un objet dans
        les rôles définis sur le système, la mesure qui dit si un objet
        critique est partout ou nulle part.

        La distinction compte : un rôle défini n'est pas un rôle attribué, et
        ce keyword mesure le premier. Mesuré sur la cible, 60793 lignes de
        rôle au total pour seulement neuf attributions effectives, donc lire
        l'un pour l'autre surestime massivement.
        """
        noms = robot_args.as_name_list(objects)
        if not noms:
            raise ValueError(
                "Count Authorization Object Usage : aucun objet demandé.")
        comptes: dict[str, int] = {}
        for nom in noms:
            rows = self.read_rfc_table("AGR_1251", ["AGR_NAME"], alias=alias,
                                       options=f"OBJECT = '{nom}'")
            comptes[nom] = len(rows)
        return comptes

    def read_role_assignments(self, alias: str = "default") -> dict[str, Any]:
        """Lit les **attributions de rôles** effectives du mandant de
        connexion, avec leur date de fin.

        Rend ``{"total", "assignments", "without_end_date", "by_user"}``.

        ``without_end_date`` isole les attributions sans échéance : sur la
        cible, les neuf le sont toutes. Ce n'est pas un défaut en soi, c'est
        une propriété à voir, parce qu'une attribution sans fin survit à la
        raison qui l'a justifiée.
        """
        rows = self.read_rfc_table(
            "AGR_USERS", ["AGR_NAME", "UNAME", "FROM_DAT", "TO_DAT"],
            alias=alias)
        attributions = [
            {"role": str(r.get("AGR_NAME", "")).strip(),
             "user": str(r.get("UNAME", "")).strip(),
             "from": str(r.get("FROM_DAT", "")).strip(),
             "to": str(r.get("TO_DAT", "")).strip()} for r in rows]
        par_user: dict[str, list[str]] = {}
        for a in attributions:
            par_user.setdefault(a["user"], []).append(a["role"])
        return {
            "total": len(attributions),
            "assignments": sorted(attributions,
                                  key=lambda a: (a["user"], a["role"])),
            "without_end_date": sorted(
                f"{a['user']}:{a['role']}" for a in attributions
                if a["to"] in ("99991231", "", "00000000")),
            "by_user": {u: sorted(r) for u, r in sorted(par_user.items())},
        }

    def read_forbidden_password_count(self, alias: str = "default") -> int:
        """Compte les entrées de la **liste des mots de passe interdits**.

        Zéro signifie qu'aucun mot de passe trivial n'est refusé par le
        système, ce qui est la mesure sur la cible. La liste ne porte que des
        empreintes, jamais de valeur lisible, donc le keyword ne rend qu'un
        décompte : c'est tout ce qui est à la fois mesurable et utile.

        Le champ projeté est ``BCODE`` et non ``BNAME`` : cette table n'a pas
        de colonne d'utilisateur, et demander la mauvaise colonne sort en
        ``TABLE_WITHOUT_DATA``, code qui ferait conclure « liste vide » sans
        avoir lu, avec ici la même réponse que la vérité.
        """
        return len(self.read_rfc_table("USR40", ["BCODE"], alias=alias))
