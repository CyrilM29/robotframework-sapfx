"""Mixin RFC et BAPI (optionnel) : pyrfc si installe, erreur actionnable sinon.

`Open Rfc Connection` / `Call Rfc` (SAP NW RFC SDK requis, jamais de
dependance dure), la perception du canal (`Get Rfc Channel Status`,
`Get Rfc Connection Attributes`, `Read Rfc Table`), la classification de ses
refus par code technique (`Rfc Should Fail With Code`) ou par identifiant de
message (`Rfc Should Fail With Message Id`). L'attente d'un job de fond
(`Wait For Background Job` et sa perception) vit dans ``_rfc_jobs.py``, et
la *surface du canal* (`Write Rfc Surface Artifact` /
`Compare Rfc Surface Artifacts`) dans ``_rfc_surface_artifact.py`` : deux
extractions du 2026-10-06, le fichier approchant la limite de 500 lignes
(convention n°13).

Le pattern *BAPI* (`Call Bapi` jugé par TYPE de BAPIRET2,
`Commit/Rollback Bapi Transaction`, refus par identifiant de message) vit
dans le mixin voisin ``_bapi.py``.

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

from typing import Any

from sapfx_common import rfc_channel, rfc_tables
from sapfx_common.secrets import reveal_secret

from ._core import _ApiCore


class RfcKeywords(_ApiCore):
    """Mixin de :class:`SapApiLibrary` : le canal RFC/BAPI optionnel."""

    #: Les appels dont un refus peut être ATTENDU par `Rfc Should Fail With
    #: Code` : la cible est nommée par le keyword qui la porte, et résolue
    #: dans la bibliothèque elle-même (aucune indirection par le runner, donc
    #: un mot de passe de type `Secret` traverse intact).
    _EXPECTABLE_CALLS = {
        "open rfc connection": "open_rfc_connection",
        "call rfc": "call_rfc",
        "read rfc table": "read_rfc_table",
        "call bapi": "call_bapi",
        "wait for background job": "wait_for_background_job",
        # Les deux keywords d'extraction (mixin voisin `_rfc_extract`) : sans
        # eux, le refus du tampon de 512 octets sur le chemin d'extraction ne
        # pourrait s'asserter que par son TEXTE, donc de façon localisée.
        "extract rfc table": "extract_rfc_table",
        "count rfc table rows": "count_rfc_table_rows",
    }

    def get_rfc_channel_status(self) -> dict[str, Any]:
        """État du canal RFC sur ce poste, *sans jamais échouer* : le
        préflight à poser avant d'ouvrir quoi que ce soit, et le pendant RFC de
        `Gateway Should Be Active`.

        Retourne ``{"available": bool, "reason", "version", "detail",
        "remediation"}``. ``reason`` distingue les deux absences qui n'ont pas
        le même remède : ``module_absent`` (le binding `pyrfc` n'est pas
        installé, souvent parce que l'interpréteur dépasse 3.12) et
        ``runtime_absent`` (le binding est là, la bibliothèque native NW RFC
        manque). Une suite RFC s'en sert pour se SAUTER proprement là où le
        canal n'existe pas, au lieu de rougir là où rien n'est cassé.

        Exemple :
        | ${channel}=    `Get Rfc Channel Status`
        | Skip If    not ${channel}[available]    ${channel}[remediation]
        """
        try:
            import pyrfc
        except Exception as err:   # ImportError, mais aussi OSError Windows
            return rfc_channel.unavailable_status(err)
        # Un import qui réussit ne suffit PAS : le __init__ de pyrfc 3.3.1
        # avale l'échec de chargement du runtime natif et rend un module sans
        # Connection (mesuré en CI le 2026-08-29). Le verdict lit le module.
        return rfc_channel.binding_status(pyrfc)

    def rfc_channel_should_be_available(self) -> dict[str, Any]:
        """Échoue si le canal RFC n'est pas utilisable sur ce poste, en nommant
        la cause ET son remède. Variante assertive de `Get Rfc Channel
        Status` : à poser quand l'absence du canal EST une anomalie (sinon,
        lire le statut et sauter).

        Exemple :
        | `Rfc Channel Should Be Available`
        """
        status = self.get_rfc_channel_status()
        if not status["available"]:
            raise AssertionError(
                "Canal RFC indisponible (%s) : %s %s"
                % (status["reason"], status["detail"], status["remediation"]))
        return status

    def open_rfc_connection(self, alias: str = "default", **params: Any) -> str:
        """Ouvre une connexion RFC via `pyrfc` (``ashost=``, ``sysnr=``,
        ``client=``, ``user=``, ``passwd=``...). Échec explicite avec la marche
        à suivre si `pyrfc`/le SDK NW RFC ne sont pas installés : le RFC reste
        *optionnel*, rien d'autre dans la bibliothèque n'en dépend.

        Exemple :
        | `Open Rfc Connection`    alias=a4h    ashost=localhost    sysnr=00    client=001
        | ...    user=DEVELOPER    passwd=${RFC_PASSWORD}    lang=EN
        """
        pyrfc = self._require_pyrfc()
        self._rfc_connections()[alias] = pyrfc.Connection(
            **{name: reveal_secret(value) for name, value in params.items()})
        return alias

    def _require_pyrfc(self) -> Any:
        """Le module `pyrfc` UTILISABLE, ou une erreur actionnable qui nomme la
        cause et son remède. Le même verdict que `Get Rfc Channel Status` :
        un import qui réussit ne suffit pas (binding importable mais vide de
        ``Connection`` = runtime natif absent, voir
        ``rfc_channel.binding_status``)."""
        try:
            import pyrfc
        except Exception as err:
            status = rfc_channel.unavailable_status(err)
        else:
            status = rfc_channel.binding_status(pyrfc)
            if status["available"]:
                return pyrfc
        raise RuntimeError(
            "Le canal RFC a besoin de pyrfc et du runtime NW RFC (%s : %s). "
            "%s Les keywords OData, eux, fonctionnent sans."
            % (status["reason"], status["detail"], status["remediation"]))

    def get_rfc_connection_attributes(self, alias: str = "default") -> dict[str, Any]:
        """Les attributs de la connexion RFC ``alias``, tels que le canal les
        rend : ``sysId``, ``client``, ``user``, ``partnerRel`` (release du
        système joint), ``kernelRel``, ``sysNumber``, ``language`` …

        C'est la *perception d'identité* du canal sans écran : un canal
        ouvert ne dit pas encore vers QUOI. Une campagne qui ne prouve pas
        l'identité de sa cible peut être verte contre le mauvais système, ce
        que ce dépôt a déjà vécu côté web avec un nom d'hôte partagé. Les
        valeurs sont converties en chaînes (retour JSON-safe, servable à un
        agent).

        Exemple :
        | ${attributes}=    `Get Rfc Connection Attributes`    alias=a4h
        | Should Be Equal    ${attributes}[client]    001
        """
        connection = self._require_rfc_connection(alias, "Get Rfc Connection Attributes")
        attributes = connection.get_connection_attributes()
        return {str(name): str(value) for name, value in dict(attributes).items()}

    def read_rfc_table(self, table: str, fields: Any, alias: str = "default",
                       options: Any = None, rowcount: int = 0,
                       delimiter: str = "|") -> list[dict[str, str]]:
        """Lit une table par ``RFC_READ_TABLE`` et rend une liste de dicts
        ``{champ: valeur}`` : le miroir sans écran de `Read Grid` (ECC) et de
        `Read Business Entities` (OData).

        ``fields`` : liste, ou chaîne séparée par des virgules. La lecture est
        toujours PROJETÉE (on ne rapatrie que les champs utiles) et bornée par
        ``rowcount`` (0 = tout). ``options`` : une clause de sélection ou une
        liste de clauses, chacune limitée à 72 caractères par le module ABAP,
        limite vérifiée AVANT tout appel réseau (au-delà, découper en clauses
        ``AND``).

        Piège de diagnostic du canal, mesuré : un nom de champ inexistant sort
        en ``TABLE_WITHOUT_DATA``, un code qui accuse la TABLE d'être vide
        alors qu'elle est pleine et que le fautif est le champ. Vérifier
        l'orthographe des champs avant de conclure à une absence de données.

        Un champ RAW (``TYPE X`` : GUID, ``NODE_KEY``) est REFUSÉ : le module le
        rend tronqué à la moitié de sa valeur, et deux lignes différentes
        peuvent alors porter la même valeur visible (mesuré sur A4H).

        Exemple :
        | ${clients}=    `Read Rfc Table`    T000    MANDT,MTEXT    alias=a4h
        | ${lufthansa}=    `Read Rfc Table`    SCARR    CARRID,CARRNAME,CURRCODE    alias=a4h
        | ...    options=CARRID = 'LH'
        | Should Be Equal    ${lufthansa}[0][CURRCODE]    EUR
        """
        params = rfc_tables.read_table_params(
            table, rfc_tables.as_field_list(fields),
            rfc_tables.as_clause_list(options),
            delimiter=delimiter, rowcount=int(rowcount))
        result = self.call_rfc("RFC_READ_TABLE", alias=alias, **params)
        raw = rfc_tables.truncated_raw_fields(result)
        if raw:
            raise AssertionError(rfc_tables.format_truncated_raw(str(table), raw))
        return rfc_tables.parse_read_table(result, delimiter=delimiter)

    def rfc_should_fail_with_code(self, expected_code: str, keyword: str,
                                  *args: Any, **params: Any) -> dict[str, Any]:
        """Vérifie qu'un appel RFC échoue avec le *code technique* attendu
        (``TABLE_NOT_AVAILABLE``, ``FU_NOT_FOUND``, ``RFC_LOGON_FAILURE`` …), et
        retourne la fiche du refus.

        C'est la convention n°3 appliquée au canal RFC : le code est stable
        d'un système et d'une langue à l'autre, le message ne l'est pas. Un
        `Run Keyword And Expect Error` ne peut pas rendre ce service, il ne
        voit que le texte.

        ``keyword`` nomme l'appel attendu en échec parmi ceux de cette
        bibliothèque : `Open Rfc Connection`, `Call Rfc`, `Read Rfc Table`,
        `Call Bapi`, `Wait For Background Job`. Les arguments qui suivent sont
        ceux de ce keyword, transmis intacts : un mot de passe de type `Secret`
        reste un `Secret`, et rien n'est journalisé.

        Deux échecs distincts, à dessein : l'appel a réussi (le refus attendu
        ne se produit plus), ou il a échoué avec un AUTRE code (les deux codes
        sont nommés). Un refus sans code technique, comme les gardes propres à
        la bibliothèque, n'est jamais confondu avec un refus du serveur.

        Exemple :
        | `Rfc Should Fail With Code`    TABLE_NOT_AVAILABLE    `Read Rfc Table`    ZZ_NO_SUCH_TABLE
        | ...    MANDT    alias=a4h
        | `Rfc Should Fail With Code`    FU_NOT_FOUND    `Call Rfc`    Z_NO_SUCH_FUNCTION    alias=a4h
        """
        expected = str(expected_code).strip()
        subject, error = self._provoke_rfc_failure(keyword, expected, args, params)
        if rfc_channel.rfc_error_code(error).upper() != expected.upper():
            raise AssertionError(
                rfc_channel.format_code_mismatch(subject, expected, error))
        return rfc_channel.describe_rfc_error(error)

    def rfc_should_fail_with_message_id(self, expected_message_id: str,
                                        keyword: str, *args: Any,
                                        **params: Any) -> dict[str, Any]:
        """Vérifie qu'un appel RFC échoue avec l'*identifiant de message*
        attendu (``DA/E/131``, ``AD/E/718``, ``FL/E/046`` …), et retourne la
        fiche du refus.

        Complément FIN de `Rfc Should Fail With Code`, et tout aussi
        indépendant de la langue : le code technique est stable mais grossier,
        alors que la classe, le type et le numéro du message ABAP désignent le
        refus exact. Les asserter ensemble caractérise un refus sans jamais
        toucher à son libellé (convention n°3).

        Mêmes arguments que `Rfc Should Fail With Code` : ``keyword`` nomme
        l'appel attendu en échec, les arguments qui suivent sont les siens et
        traversent intacts. Un refus qui ne porte AUCUN identifiant de message
        (refus du runtime client, garde de la bibliothèque) échoue en le
        disant, plutôt que de se comparer à du vide. Le refus d'une BAPI dans
        sa table ``RETURN`` n'est pas une exception RFC : l'asserter par
        `Bapi Should Fail With Message Id`.

        Exemple :
        | `Rfc Should Fail With Message Id`    FL/E/046    `Call Rfc`    Z_NO_SUCH_FUNCTION    alias=a4h
        | `Rfc Should Fail With Message Id`    DA/E/131    `Read Rfc Table`    ZZ_NO_SUCH_TABLE    MANDT
        | ...    alias=a4h
        """
        expected = str(expected_message_id).strip()
        subject, error = self._provoke_rfc_failure(keyword, expected, args, params)
        described = rfc_channel.describe_rfc_error(error)
        if described["message_id"].upper() != expected.upper():
            raise AssertionError(
                rfc_channel.format_message_id_mismatch(subject, expected, error))
        return described

    def _provoke_rfc_failure(self, keyword: str, expected: str,
                             args: tuple[Any, ...],
                             params: dict[str, Any]) -> tuple[str, BaseException]:
        """Provoque l'appel ``keyword`` en ATTENDANT son échec, et rend
        ``(sujet, exception)``. Le socle commun des deux oracles de refus
        (`Rfc Should Fail With Code` et `Rfc Should Fail With Message Id`) :
        résolution de la cible, exécution, et le cas de l'appel qui RÉUSSIT là
        où un refus était attendu, qui mérite son propre message parce qu'un
        oracle vert parce que rien n'a échoué ne prouve rien."""
        target = self._EXPECTABLE_CALLS.get(
            " ".join(str(keyword).replace("_", " ").lower().split()))
        if target is None:
            raise ValueError(
                "Un oracle de refus RFC ne sait pas provoquer '%s'. Appels "
                "attendus en échec : %s." % (keyword, ", ".join(
                    sorted(name.title() for name in self._EXPECTABLE_CALLS))))
        subject = "L'appel « %s »" % str(keyword).strip()
        try:
            result = getattr(self, target)(*args, **params)
        except Exception as err:   # noqa: BLE001 : c'est le refus attendu
            return subject, err
        if target == "open_rfc_connection":
            # Une ouverture qui réussit là où un refus était attendu laisserait
            # une session utilisateur ouverte côté serveur : la refermer AVANT
            # de rapporter l'échec.
            self.close_rfc_connection(str(result))
        raise AssertionError(rfc_channel.format_missing_failure(subject, expected))

    def _require_rfc_connection(self, alias: str, keyword: str) -> Any:
        """La connexion RFC ``alias``, ou une erreur qui nomme le keyword
        d'ouverture (le refus le plus fréquent du canal : un alias jamais
        ouvert, ou déjà fermé par un teardown)."""
        connection = self._rfc_connections().get(alias)
        if connection is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord (%s)." % (alias, keyword))
        return connection

    def call_rfc(self, function_name: str, alias: str = "default",
                 **params: Any) -> Any:
        """Appelle le module fonction ``function_name`` sur la connexion RFC
        ``alias`` (ouverte par `Open Rfc Connection`) et retourne le résultat
        (dict pyrfc).

        Deux règles de la frontière Robot vers ABAP, la première tenue ici, la
        seconde à la charge de l'appelant : les structures et les tables sont
        ramenées à des types nus (un dictionnaire construit dans une suite est
        un ``DotDict``, que `pyrfc` refuse pour un paramètre de structure) ;
        en revanche un paramètre NUMÉRIQUE doit être passé comme un vrai
        nombre (``${3}``, pas ``3``), car deviner le type d'après la forme de
        la chaîne corromprait les champs caractère numériques, où ``'0400'``
        est un numéro de liaison et non l'entier 400.

        Exemple :
        | ${info}=    `Call Rfc`    RFC_SYSTEM_INFO    alias=a4h
        | Should Be Equal    ${info}[RFCSI_EXPORT][RFCSYSID]    A4H
        | ${echo}=    `Call Rfc`    STFC_CONNECTION    alias=a4h    REQUTEXT=hello
        | Should Be Equal    ${echo}[ECHOTEXT]    hello
        """
        connection = self._require_rfc_connection(alias, "Call Rfc")
        return connection.call(
            function_name, **rfc_channel.plain_rfc_parameters(params))

    def close_rfc_connection(self, alias: str = "default") -> None:
        """Ferme la connexion RFC ``alias`` (silencieux si absente).

        Exemple :
        | `Close Rfc Connection`    a4h
        """
        connection = self._rfc_connections().pop(alias, None)
        if connection is not None:
            connection.close()
