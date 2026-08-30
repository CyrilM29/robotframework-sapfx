---
name: pyrfc-import-vert-module-vide
description: 2026-08-29, sur un poste sans runtime NW RFC, `import pyrfc` RÉUSSIT (le __init__ de pyrfc 3.3.1 avale l'échec de chargement natif et l'imprime sans le relever) et rend un module sans Connection ; tout préflight fondé sur « l'import passe » ou « l'import échoue » se trompe dans un sens ou dans l'autre
type: projet
date: 2026-08-29
---

À la PREMIÈRE exécution réelle du préflight CI « binding présent, runtime
natif absent » (un runner sans SDK où l'on installe la roue précompilée),
l'étape a échoué sur sa propre hypothèse : elle attendait un `import pyrfc`
en échec, et l'import est sorti en code 0, le message « DLL load failed while
importing _cyrfc » restant visible MALGRÉ une redirection de stderr.

La cause se lit dans le `__init__.py` du wheel pyrfc 3.3.1 : l'import des
symboles natifs est enveloppé dans `except Exception as ex: print(ex)`. Sur
un poste sans `sapnwrfc.dll`, l'import du paquet RÉUSSIT donc (le message
part sur stdout, d'où sa visibilité), et le module rendu ne porte ni
`Connection` ni aucun symbole natif.

**Pourquoi :** deux erreurs symétriques en découlent. Un préflight qui fait
confiance à un import vert déclare le canal DISPONIBLE là où il ne l'est
pas : la suite RFC rougit au lieu de se sauter, et l'ouverture de connexion
meurt en `AttributeError: module 'pyrfc' has no attribute 'Connection'`, qui
ne nomme ni cause ni remède. Et un contrôle qui attend un import ROUGE
(l'étape CI d'origine) échoue lui aussi, sur un poste pourtant exactement
dans l'état visé. Le développement ne pouvait pas voir le piège : sur un
poste porteur de SAP GUI, le runtime est là et l'import est complet
([[sap-gui-fournit-le-runtime-rfc]]).

**Comment appliquer :** juger le canal sur le CONTENU du module, jamais sur
le sort de l'import : `getattr(pyrfc, "Connection", None)` absent = runtime
natif absent (même remède que l'échec de chargement franc). Dans un script,
importer le symbole nommément (`from pyrfc import Connection`), forme qui
échoue franchement sur un module avalé. Et se méfier de tout diagnostic
fondé sur « l'erreur part sur stderr » : ici elle part sur stdout.
