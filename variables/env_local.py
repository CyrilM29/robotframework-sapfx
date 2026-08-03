"""Données d'environnement — cible **locale** cap-sflight (`npx cds watch`).

Ce que ce fichier porte : les adresses et identifiants techniques d'un
environnement, pas des localisateurs (ils vivent dans
``resources/page_objects/``) ni des données métier (elles vivent dans la suite
ou dans ``resources/``).

Format Python et non YAML, volontairement : un fichier de variables ``.py``
n'ajoute **aucune dépendance** au projet, là où un ``.yaml`` exigerait PyYAML
dans ``requirements.txt``.

Aucun secret ici — la cible cap-sflight locale ne demande aucune
authentification. Un mot de passe ne se met JAMAIS dans un fichier de
variables : il se passe en ligne de commande, typé Secret
(``-v "SAP_PASSWORD: Secret:…"``), pour rester masqué jusqu'au niveau TRACE.

Surcharge possible sans toucher au fichier ::

    robot -v TRAVEL_APP_URL:http://autre-hote:4004/sap.fe.cap.travel/index.html …
"""

# Application Fiori Elements v4 « Travel processor » (`sap.fe.cap.travel`,
# vue TravelList) servie par `npx cds watch` sur le port 4004.
TRAVEL_APP_URL = "http://localhost:4004/sap.fe.cap.travel/index.html"
