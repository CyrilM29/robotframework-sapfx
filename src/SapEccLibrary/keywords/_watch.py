"""Mixin sentinelle de derive : surveiller un ecran SANS test scripte.

`Check Screen Against Watch` croise TROIS canaux contre une reference
memorisee (``sapfx_common.screen_watch``) : diff structurel intelligent
(renommages apparies par le scoring de healing), distance visuelle globale,
et grille de tuiles (la derive locale trop diluee pour le hash global est
rattrapee par SA tuile, nommee avec rectangle et elements recouvrants).
Premiere visite = reference creee a committer ; ensuite chaque ecart est
nomme et la perception courante sauvee en ``<name>.actual.*``. Harnais :
``tests/robot/ecc_drift_sentinel.robot``.

Extrait de ``_perception.py`` (convention #13).
"""
import base64

from robot.api import logger

from ._perception import _TRUTHY


class WatchKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : compare l'écran
    à sa référence, n'écrit que dans le répertoire de la sentinelle."""

    def check_screen_against_watch(self, name, directory="screen_watch",
                                   fail_on_drift=False, visual_threshold=5,
                                   tiles_x=4, tiles_y=4, per_resolution=False):
        """**Sentinelle** : compare l'écran SAP actif à sa référence mémorisée,
        la détection de dérive SANS test scripté (voir
        ``sapfx_common.screen_watch``).

        Première visite de ``name`` : la perception structurée (et les
        empreintes visuelles, hash global + grille de tuiles, si Pillow est
        présent) devient la référence dans ``directory`` : WARNING journalisé,
        statut ``baseline-created``. Ensuite, TROIS canaux :

        * **structurel** : diff *intelligent* ligne à ligne (les ids qui se
          ressemblent sont appariés en ``~ ancien -> nouveau`` par le scoring
          de healing : un sous-écran renuméroté se lit comme un renommage) ;
        * **visuel global** : distance de Hamming du hash plein écran ;
        * **visuel localisé** : comparaison tuile à tuile (grille ``tiles_x ×
          tiles_y``, défaut 4×4) : une dérive locale trop diluée pour le hash
          global est rattrapée par SA tuile, nommée avec sa position, son
          rectangle et les éléments qui la recouvrent.

        Toute dérive est **nommée** et la perception courante sauvée en
        ``<name>.actual.*`` à côté de la référence. ``fail_on_drift=True``
        transforme la dérive en échec (sentinelle-assertion) ; par défaut la
        sentinelle **rapporte** et retourne le verdict (dict : ``status``,
        ``structural_diff``, ``visual_distance``, ``visual_tiles``) ; c'est au
        run de veille d'agréger.

        ``per_resolution=True`` donne à chaque **géométrie de capture** sa
        propre référence VISUELLE (``<name>@1920x1032.dhash.txt`` et
        ``.tiles.txt``), le canal structurel restant partagé : une signature
        d'écran ne dépend pas de la résolution, une empreinte perceptuelle si.
        Un poste dont la géométrie n'a pas encore de référence visuelle
        l'enregistre (WARNING) et ne compare que le structurel ce passage-là,
        au lieu de rapporter une dérive qui n'est qu'un changement d'échelle.
        Une référence déjà committée reste utilisée tant que sa géométrie
        coïncide. Sans l'option, une dérive visuelle dont les géométries
        diffèrent le **dit** dans le verdict (``geometry_note``).

        La référence est faite pour être committée : la supprimer revalide
        l'écran au passage suivant (même sémantique snapshot que
        `Screen Should Match Baseline`, ici sur TOUS les canaux)."""
        import os
        from sapfx_common.screen_watch import (WatchOutcome, annotate_geometry,
                                               apply_tile_verdict,
                                               compare_watch,
                                               parse_dhash_reference)
        from sapfx_common.visual_baseline import (format_geometry,
                                                  validate_snapshot_name)
        safe = validate_snapshot_name(name, kind="surveillance")
        per_geometry = str(per_resolution).strip().lower() in _TRUTHY
        signature = self.get_screen_signature()
        fingerprint = self._try_visual_fingerprint()
        visual, geometry = fingerprint if fingerprint else (None, None)
        directory = os.path.abspath(str(directory))
        signature_path = os.path.join(directory, "%s.signature.txt" % safe)
        hash_path, tiles_path = self._watch_visual_paths(
            directory, safe, geometry, per_geometry)
        if not os.path.exists(signature_path):
            os.makedirs(directory, exist_ok=True)
            with open(signature_path, "w", encoding="utf-8") as fh:
                fh.write(signature)
            self._write_watch_visual(hash_path, visual, geometry, tiles_path,
                                     int(tiles_x), int(tiles_y))
            logger.warn("Sentinelle : référence '%s' créée (%s), première "
                        "visite, à committer si l'écran fait référence."
                        % (safe, signature_path))
            outcome = WatchOutcome(name=safe, status="baseline-created")
            return self._watch_outcome_dict(outcome)
        with open(signature_path, "r", encoding="utf-8") as fh:
            baseline_signature = fh.read()
        baseline_hash, reference_geometry = None, None
        if os.path.exists(hash_path):
            with open(hash_path, "r", encoding="utf-8") as fh:
                baseline_hash, reference_geometry = parse_dhash_reference(fh.read())
            if reference_geometry is None:
                reference_geometry = self._watch_tiles_geometry(tiles_path)
        elif visual and geometry:
            # Géométrie encore inconnue de la surveillance : on ENREGISTRE sa
            # référence visuelle (le canal structurel, lui, compare déjà).
            self._write_watch_visual(hash_path, visual, geometry, tiles_path,
                                     int(tiles_x), int(tiles_y))
            logger.warn("Sentinelle : référence visuelle de la géométrie %s "
                        "créée pour '%s' (%s), à committer ; ce passage compare "
                        "le canal structurel seul."
                        % (format_geometry(geometry), safe, hash_path))
        outcome = compare_watch(safe, baseline_signature, signature,
                                baseline_hash, visual,
                                int(visual_threshold))
        tile_report = self._tile_drift_report(tiles_path, int(visual_threshold))
        outcome = apply_tile_verdict(outcome, tile_report)
        outcome = annotate_geometry(outcome, reference_geometry, geometry,
                                    per_geometry)
        if outcome.drifted:
            actual_path = os.path.join(directory, "%s.actual.signature.txt" % safe)
            with open(actual_path, "w", encoding="utf-8") as fh:
                fh.write(signature)
            details = "\n".join(part for part in (
                outcome.structural_diff,
                ("distance visuelle %d bits" % outcome.visual_distance)
                if outcome.visual_distance is not None else None,
                outcome.visual_tiles, outcome.geometry_note) if part)
            message = ("Sentinelle : l'écran '%s' a DÉRIVÉ de sa référence.\n"
                       "%s\nPerception courante sauvée : %s"
                       % (safe, details, actual_path))
            if str(fail_on_drift).strip().lower() in _TRUTHY:
                self.take_screenshot()
                raise AssertionError(message)
            logger.warn(message)
        else:
            logger.info("Sentinelle : écran '%s' inchangé." % safe)
        return self._watch_outcome_dict(outcome)

    def _watch_visual_paths(self, directory, safe, geometry, per_geometry):
        """Décide OÙ vivent les références visuelles de la surveillance.

        Sans ``per_resolution`` : les fichiers historiques, partagés. Avec : la
        variante de la géométrie courante si elle existe, sinon les fichiers
        historiques **à condition** que leur géométrie coïncide (ou soit
        inconnue : une référence d'avant l'ajout du champ reste utilisée telle
        quelle, comme avant), sinon la variante, qui sera créée."""
        import os
        plain = (os.path.join(directory, "%s.dhash.txt" % safe),
                 os.path.join(directory, "%s.tiles.txt" % safe))
        if not per_geometry or not geometry:
            return plain
        from sapfx_common.visual_baseline import format_geometry
        suffix = format_geometry(geometry)
        variant = (os.path.join(directory, "%s@%s.dhash.txt" % (safe, suffix)),
                   os.path.join(directory, "%s@%s.tiles.txt" % (safe, suffix)))
        if os.path.exists(variant[0]):
            return variant
        if os.path.exists(plain[0]):
            from sapfx_common.screen_watch import parse_dhash_reference
            with open(plain[0], "r", encoding="utf-8") as fh:
                known = parse_dhash_reference(fh.read())[1]
            if known is None:
                known = self._watch_tiles_geometry(plain[1])
            if known is None or known == geometry:
                return plain
        return variant

    @staticmethod
    def _watch_tiles_geometry(tiles_path):
        """Géométrie inscrite dans l'en-tête d'un ``*.tiles.txt`` : le témoin
        des références écrites avant que le ``.dhash.txt`` ne porte la sienne.
        ``None`` si le fichier est absent ou illisible."""
        import os
        if not os.path.exists(tiles_path):
            return None
        from sapfx_common.screen_watch import parse_tiles_reference
        with open(tiles_path, "r", encoding="utf-8") as fh:
            reference = parse_tiles_reference(fh.read())
        return reference.geometry if reference else None

    def _write_watch_visual(self, hash_path, visual, geometry, tiles_path,
                            tiles_x, tiles_y):
        """Écrit les deux références VISUELLES d'un écran surveillé (empreinte
        plein écran avec sa géométrie, grille de tuiles), chacune seulement si
        son canal a pu être capté : le canal structurel, lui, suffit à faire
        marcher la sentinelle."""
        from sapfx_common.screen_watch import (format_dhash_reference,
                                               format_tiles_reference)
        if visual:
            with open(hash_path, "w", encoding="utf-8") as fh:
                fh.write(format_dhash_reference(visual, geometry))
        tiles = self._try_tile_capture(tiles_x, tiles_y)
        if tiles:
            tile_hashes, width, height = tiles
            with open(tiles_path, "w", encoding="utf-8") as fh:
                fh.write(format_tiles_reference(tile_hashes, tiles_x, tiles_y,
                                                8, (width, height)))

    def _try_visual_fingerprint(self):
        """Empreinte visuelle **best-effort** : ``(hash, (largeur, hauteur))``
        en UNE capture, ou ``None``. La sentinelle reste utilisable sans Pillow
        (canal structurel seul) et sur les SAP GUI sans HardCopyToMemory ; la
        géométrie voyage avec l'empreinte parce que c'est elle qui dit à quel
        poste une référence visuelle vaut."""
        try:
            png = base64.b64decode(self.get_screenshot_as_base64("png"))
            pixels = self._decode_image_to_gray(png)
            from sapfx_common.visual_hash import dhash_hex
            from sapfx_common.visual_baseline import geometry_of
            return dhash_hex(pixels), geometry_of(pixels)
        except Exception:
            return None

    def _try_tile_capture(self, tiles_x, tiles_y, hash_size=8):
        """Grille de tuiles **best-effort** : ``(hashes, largeur, hauteur)`` ou
        ``None``, même politique que ``_try_visual_fingerprint`` (le canal tuiles
        est un raffinement, jamais une condition de fonctionnement)."""
        try:
            png = base64.b64decode(self.get_screenshot_as_base64("png"))
            pixels = self._decode_image_to_gray(png)
            from sapfx_common.visual_hash import tiled_dhash
            hashes = tiled_dhash(pixels, tiles_x, tiles_y, hash_size)
            return hashes, (len(pixels[0]) if pixels else 0), len(pixels)
        except Exception:
            return None

    def _tile_drift_report(self, tiles_path, visual_threshold):
        """Compare l'écran courant à la grille de tuiles de la référence, avec
        le découpage ET le hash_size **de la référence** (un changement de
        configuration ne fabrique jamais une fausse dérive). Retourne le
        rapport localisé (tuiles au-delà du seuil + éléments recouvrants) ou
        ``None``, best-effort intégral."""
        import os
        if not os.path.exists(tiles_path):
            return None
        from sapfx_common.screen_watch import parse_tiles_reference
        with open(tiles_path, "r", encoding="utf-8") as fh:
            reference = parse_tiles_reference(fh.read())
        if reference is None:
            return None
        btx, bty = reference.tiles_x, reference.tiles_y
        baseline_tiles = reference.hashes
        current = self._try_tile_capture(btx, bty, reference.hash_size)
        if current is None:
            return None
        current_tiles, width, height = current
        if len(current_tiles) != len(baseline_tiles):
            return None
        from sapfx_common.screen_watch import locate_tile_drift
        from sapfx_common.visual_hash import tiled_hamming
        try:
            distances = tiled_hamming(baseline_tiles, current_tiles)
        except ValueError:
            return None
        if max(distances, default=0) <= visual_threshold:
            return None
        ox, oy = self._window_origin()
        elements = [
            (el.id, el.left - ox, el.top - oy, el.width, el.height)
            for el in self._screen_elements()
            if el.left is not None and el.top is not None
            and el.width and el.height
        ]
        return locate_tile_drift(distances, btx, bty, width, height,
                                 visual_threshold, elements) or None

    @staticmethod
    def _watch_outcome_dict(outcome):
        """Le verdict en dict de chaînes/entiers : MCP-safe, lisible en Robot."""
        return {"name": outcome.name, "status": outcome.status,
                "structural_diff": outcome.structural_diff,
                "visual_distance": outcome.visual_distance,
                "visual_tiles": outcome.visual_tiles,
                "geometry_note": outcome.geometry_note}
