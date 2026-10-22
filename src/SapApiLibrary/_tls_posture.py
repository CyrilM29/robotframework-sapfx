"""Mixin de la *posture TLS* d'un système ABAP : le certificat que STRUST
déclare, les services que l'ICM sert, et le certificat présenté sur le fil.

Né du scénario 12 (2026-10-08, ABAP Platform 2023, release 758). Trois canaux
disent trois choses différentes, et seule leur confrontation répond à la
question « le certificat serveur est-il valide et réellement servi ? » :

- le canal RFC lit le certificat propre d'une identité STRUST
  (``SSFR_GET_OWNCERTIFICATE`` puis ``SSFR_PARSE_CERTIFICATE`` : dates en temps
  ASN.1 UTC, indépendantes du format de date de l'utilisateur) et l'état des
  services de l'ICM (``ICM_GET_INFO``, drapeau ``ACTIVE``) ;
- le fil montre le certificat que l'ICM PRÉSENTE pendant la poignée de main
  TLS, comparé à celui de STRUST par son empreinte SHA-256.

Deux pièges mesurés : une identité STRUST sans PSE ne lève RIEN (un DER vide
et un message ``1S/E/406`` dans la table de retour), donc chaque lecture juge
la table de retour avant le résultat ; et les deux conteneurs du banc portent
le même certificat et les mêmes services, donc rien ici ne prouve la cible.

Logique pure dans ``sapfx_common.tls_certificates``. Ajouté à côté de
``_http_security.py`` plutôt que dedans (convention #13) : celui-là observe
les cookies et en-têtes, celui-ci le certificat et les services.
"""
from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Optional

from robot.utils import timestr_to_secs

from sapfx_common import tls_certificates as tls

from ._rfc_gateway import RfcGatewayKeywords


class TlsPostureKeywords(RfcGatewayKeywords):
    """Mixin de :class:`SapApiLibrary` : certificat STRUST, services ICM, fil TLS."""

    def list_strust_identities(self, alias: str = "default") -> list[dict[str, str]]:
        """Liste les identités du magasin STRUST par RFC
        (``SSFR_GET_ALL_STRUST_IDENTITIES``) : ``{identity, context,
        application, tree_key, description}``, dans l'ordre de l'arbre de
        STRUST. ``identity`` (``SSLS/DFAULT``) est ce que prennent les autres
        keywords ; ``tree_key`` (``SSLSDFAULT``) est la clé du nœud dans l'arbre
        de l'écran. Un message bloquant du module fait échouer en le nommant.

        Une identité LISTÉE n'a pas forcément de PSE : la liste vient de la
        configuration, le PSE de la base (`Strust Identity Exists`).

        Exemple :
        | ${identities}=    `List Strust Identities`    alias=tls12
        | ${keys}=    Evaluate    [i['identity'] for i in $identities]
        | Should Contain    ${keys}    SSLS/DFAULT
        """
        result = self.call_rfc("SSFR_GET_ALL_STRUST_IDENTITIES", alias=alias)
        errors = tls.bapiret_errors(result.get("ET_BAPIRET2"))
        if errors:
            raise AssertionError("Lecture des identités STRUST refusée : %s"
                                 % ", ".join(e["identity"] for e in errors))
        return tls.normalize_strust_identities(result.get("ET_STRUST_IDENTITIES"))

    def _own_certificate_der(self, identity: str, alias: str) -> tuple[str, bytes, list]:
        context, application = tls.strust_identity(identity)
        name = "%s/%s" % (context, application)
        result = self.call_rfc("SSFR_GET_OWNCERTIFICATE", alias=alias,
                               IS_STRUST_IDENTITY={"PSE_CONTEXT": context,
                                                   "PSE_APPLIC": application})
        der = result.get("EV_CERTIFICATE") or b""
        return name, bytes(der), tls.bapiret_errors(result.get("ET_BAPIRET2"))

    def strust_identity_exists(self, identity: str, alias: str = "default") -> bool:
        """Vrai si l'identité STRUST ``identity`` (``SSLS/DFAULT`` ou la clé
        d'arbre ``SSLSDFAULT``) porte un certificat propre en base, faux si le
        module répond qu'elle n'a pas de PSE (``1S/E/406``). Ne fait jamais
        échouer pour cette absence ; tout autre refus du module, si.

        Exemple :
        | ${exists}=    `Strust Identity Exists`    SSLS/ANONYM    alias=tls12
        | Should Not Be True    ${exists}
        """
        _, der, errors = self._own_certificate_der(identity, alias)
        if any(e["identity"] == "1S/E/406" for e in errors):
            return False
        if errors:
            raise AssertionError("Lecture du certificat STRUST %s refusée : %s"
                                 % (identity, ", ".join(e["identity"] for e in errors)))
        return bool(der)

    def get_strust_own_certificate(self, identity: str, alias: str = "default") -> dict[str, Any]:
        """Lit le *certificat propre* d'une identité STRUST par RFC et rend
        ``{identity, subject, issuer, self_signed, serial, valid_from,
        valid_to, valid_from_raw, valid_to_raw, algorithm, der_sha256,
        der_sha1, der_length}``. ``der_sha1`` est l'empreinte que STRUST
        AFFICHE (« Checksum (SHA1) », en hexadécimal à deux-points) : elle
        relie l'écran au certificat lu par RFC. ``valid_from`` et ``valid_to`` sont en ISO UTC, lus en temps
        ASN.1 (``20380101000001Z``) : ni la langue ni le format de date de
        l'utilisateur n'y entrent, à l'inverse de l'écran de STRUST.

        ``identity`` : ``SSLS/DFAULT`` (le PSE « SSL server Standard ») ou la
        clé d'arbre ``SSLSDFAULT``. Une identité sans PSE (``1S/E/406``), un DER
        vide ou une analyse sans dates lèvent ``StrustIdentityNotFoundError``
        en nommant la cause et les identités existantes : ce keyword ne rend
        jamais une fiche aux dates vides, qu'une garde d'échéance lirait comme
        un certificat sans problème.

        Exemple :
        | ${cert}=    `Get Strust Own Certificate`    SSLS/DFAULT    alias=tls12
        | Should Be Equal    ${cert}[valid_to]    2038-01-01T00:00:01+00:00
        | Should Be True    ${cert}[self_signed]
        """
        name, der, errors = self._own_certificate_der(identity, alias)
        if errors or not der:
            known = ", ".join(i["identity"] for i in self.list_strust_identities(alias=alias))
            cause = (", ".join(e["identity"] for e in errors) if errors
                     else "certificat vide sans message")
            raise tls.StrustIdentityNotFoundError(
                "L'identité STRUST %s n'a pas de certificat propre lisible (%s). Identités "
                "configurées : %s." % (name, cause, known))
        parsed = self.call_rfc("SSFR_PARSE_CERTIFICATE", alias=alias, IV_CERTIFICATE=der)
        parse_errors = tls.bapiret_errors(parsed.get("ET_BAPIRET2"))
        if parse_errors:
            raise tls.StrustIdentityNotFoundError(
                "Le certificat de l'identité STRUST %s ne s'analyse pas : %s."
                % (name, ", ".join(e["identity"] for e in parse_errors)))
        return tls.describe_certificate(name, der, parsed)

    def get_certificate_expiry_verdict(self, valid_to: str, valid_from: Optional[str] = None,
                                       warning_days: int = 30,
                                       now: Optional[str] = None) -> dict[str, Any]:
        """Rend le verdict d'échéance d'un certificat SANS échouer :
        ``{verdict, valid_to, valid_from, now, days_remaining, warning_days}``,
        ``verdict`` valant ``valid``, ``expiring``, ``expired``,
        ``not_yet_valid`` ou ``unknown``. Pour éprouver une garde à un instant
        donné et asserter le verdict EXACT ; la garde elle-même est
        `Certificate Expiry Should Be Valid`.

        Exemple :
        | ${verdict}=    `Get Certificate Expiry Verdict`    20380101000001Z    valid_from=20170404065301Z    warning_days=30    now=2037-12-02T00:00:01Z
        | Should Be Equal    ${verdict}[verdict]    valid
        | ${verdict}=    `Get Certificate Expiry Verdict`    20380101000001Z    valid_from=20170404065301Z    warning_days=30    now=2037-12-02T00:00:02Z
        | Should Be Equal    ${verdict}[verdict]    expiring
        """
        return tls.certificate_expiry_verdict(_asn1(valid_to), _asn1(valid_from), warning_days, now)

    def certificate_expiry_should_be_valid(self, valid_to: str, valid_from: Optional[str] = None,
                                           warning_days: int = 30, now: Optional[str] = None,
                                           subject: str = "le certificat") -> dict[str, Any]:
        """Juge une échéance de certificat et échoue sauf verdict ``valid`` :
        ``expired``, ``expiring`` (moins de ``warning_days`` jours),
        ``not_yet_valid`` et ``unknown`` (échéance absente) échouent en nommant
        l'échéance MESURÉE, l'instant de référence et le seuil. Rend le verdict
        (``days_remaining`` compris).

        Dates en temps ASN.1 (``20380101000001Z``) ou ISO. ``now`` (ISO) fixe
        l'instant de référence : c'est ainsi qu'on voit la garde MORDRE sans
        toucher au certificat (``now=2038-01-02`` rend ``expired``).

        Exemple :
        | ${verdict}=    `Certificate Expiry Should Be Valid`    20380101000001Z    valid_from=20170404065301Z    warning_days=30
        | Should Be True    ${verdict}[days_remaining] > 30
        | Run Keyword And Expect Error    STARTS: Le certificat est EXPIRÉ    `Certificate Expiry Should Be Valid`    20380101000001Z    now=2038-01-02
        """
        verdict = self.get_certificate_expiry_verdict(valid_to, valid_from, warning_days, now)
        if verdict["verdict"] != "valid":
            raise AssertionError(tls.describe_expiry_failure(subject, verdict))
        return verdict

    def strust_certificate_should_be_valid(self, identity: str, warning_days: int = 30,
                                           now: Optional[str] = None,
                                           alias: str = "default") -> dict[str, Any]:
        """Lit le certificat propre de l'identité STRUST ``identity`` par RFC
        (`Get Strust Own Certificate`) et échoue sauf s'il est valide au moins
        ``warning_days`` jours encore, en nommant l'identité, l'échéance
        mesurée et le seuil. Rend ``{certificate, verdict}``. Une identité sans
        certificat échoue aussi (jamais un « valide » faute de date).

        Exemple :
        | ${checked}=    `Strust Certificate Should Be Valid`    SSLS/DFAULT    warning_days=30    alias=tls12
        | Should Be Equal    ${checked}[verdict][verdict]    valid
        """
        certificate = self.get_strust_own_certificate(identity, alias=alias)
        verdict = self.certificate_expiry_should_be_valid(
            certificate["valid_to_raw"], certificate["valid_from_raw"], warning_days, now,
            subject="le certificat STRUST %s (%s)" % (certificate["identity"],
                                                       certificate["subject"]))
        return {"certificate": certificate, "verdict": verdict}

    def read_icm_services(self, alias: str = "default") -> dict[str, Any]:
        """Lit les services de l'ICM par RFC (``ICM_GET_INFO``) et rend
        ``{status_code, services}``, chaque service ``{protocol,
        protocol_code, port, host, active, keep_alive, processing_timeout,
        external_bind}``. Le protocole est nommé par la carte relevée
        (1 HTTP, 2 HTTPS, 4 SMTP) ; un code inconnu rend ``unmapped``.

        Le port est celui que l'ICM DÉCLARE dans le conteneur ou le serveur :
        une publication sur un autre port de l'hôte (50101 pour 50001 sur le
        banc) n'y apparaît pas. Ce que SMICM affiche, l'état actif compris, que
        l'écran ne rend que par une icône.

        Exemple :
        | ${icm}=    `Read Icm Services`    alias=tls12
        | ${https}=    Evaluate    [s for s in $icm['services'] if s['protocol'] == 'HTTPS']
        | Should Be Equal    ${https}[0][port]    50001
        """
        return tls.normalize_icm_services(self.call_rfc("ICM_GET_INFO", alias=alias))

    def icm_service_should_be_active(self, protocol: str, port: Optional[str] = None,
                                     alias: str = "default") -> dict[str, Any]:
        """Échoue sauf si l'ICM déclare un service ``protocol`` (``HTTPS``...)
        ACTIF sur ``port`` (tout port sans lui), en distinguant le service
        déclaré mais INACTIF du service ABSENT, et en listant tous les services
        avec leur état. Rend le service trouvé.

        ``port`` est le port de l'ICM, pas sa publication sur l'hôte : sur le
        banc, ``HTTPS 50101`` est ABSENT de l'ICM, qui sert 50001.

        Exemple :
        | ${service}=    `Icm Service Should Be Active`    HTTPS    port=50001    alias=tls12
        | Should Be True    ${service}[active]
        | Run Keyword And Expect Error    STARTS: Service ICM HTTP sur le port 8101 déclaré mais INACTIF    `Icm Service Should Be Active`    HTTP    port=8101    alias=tls12
        """
        services = self.read_icm_services(alias=alias)["services"]
        verdict = tls.icm_service_verdict(services, protocol, port)
        if verdict["verdict"] != "active":
            raise AssertionError(tls.describe_icm_service_failure(verdict, services))
        return next(s for s in verdict["matches"] if s.get("active"))

    def get_served_tls_certificate(self, host: str, port: Any, server_name: Optional[str] = None,
                                   timeout: str = "10s") -> dict[str, Any]:
        """Établit une poignée de main TLS avec l'hôte ``host`` sur le port ``port`` et rend le
        certificat que le serveur PRÉSENTE : ``{host, port, der_sha256,
        der_length, tls_version, cipher}``. Aucun identifiant n'est envoyé,
        aucune requête HTTP n'est faite ; la chaîne n'est PAS vérifiée (le but
        est d'observer le certificat, auto-signé compris, pas de s'y fier).

        Comparer ``der_sha256`` à celui de `Get Strust Own Certificate` dit si
        le certificat servi est celui que STRUST déclare. Connexion refusée,
        délai dépassé et port sans TLS échouent chacun en le nommant.

        Exemple :
        | ${served}=    `Get Served Tls Certificate`    localhost    50101
        | ${cert}=    `Get Strust Own Certificate`    SSLS/DFAULT    alias=tls12
        | Should Be Equal    ${served}[der_sha256]    ${cert}[der_sha256]
        """
        number = int(str(port).strip())
        seconds = timestr_to_secs(timeout)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        where = "%s:%d" % (host, number)
        try:
            with socket.create_connection((host, number), timeout=seconds) as raw:
                with context.wrap_socket(raw, server_hostname=server_name or host) as wrapped:
                    der = wrapped.getpeercert(binary_form=True) or b""
                    version = wrapped.version()
                    cipher = (wrapped.cipher() or ("",))[0]
        except ConnectionRefusedError as exc:
            raise AssertionError("Connexion TLS refusée par %s : rien n'écoute sur ce port." % where) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise AssertionError("Poignée de main TLS avec %s : délai de %s dépassé." % (where, timeout)) from exc
        except ssl.SSLError as exc:
            raise AssertionError("%s ne parle pas TLS (ou refuse la poignée de main) : %s" % (where, exc)) from exc
        except OSError as exc:
            raise AssertionError("Connexion TLS impossible vers %s : %s" % (where, exc)) from exc
        if not der:
            raise AssertionError("%s n'a présenté aucun certificat pendant la poignée de main." % where)
        return {"host": host, "port": number, "der_sha256": tls.certificate_fingerprint(der),
                "der_length": len(der), "tls_version": version, "cipher": cipher}


def _asn1(value: Any) -> Any:
    """Une date ISO (``2038-01-01T00:00:01+00:00``) ramenée au temps ASN.1 ;
    le temps ASN.1 et le vide passent tels quels."""
    text = "" if value is None else str(value).strip()
    if ("-" in text and "T" in text) or (len(text) == 10 and text.count("-") == 2):
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        moment = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).strftime("%Y%m%d%H%M%SZ")
    return value
