# Un en-tête HTTP posé par urllib ne garde pas sa casse

**2026-08-22, ajout de l'authentification par clé d'API au canal API.** Le bac
à sable SAP Business Accelerator Hub s'authentifie par un en-tête nommé
`APIKey`. La session le pose correctement (`session.headers` contient bien
`{'APIKey': ...}`), et pourtant les deux tests unitaires écrits pour le
verrouiller échouaient tous les deux.

Deux comportements se cumulent, aucun des deux n'étant visible dans le code de
la bibliothèque :

1. **`urllib.request.Request` normalise le nom de tout en-tête qu'on lui
   confie.** `add_header` stocke la forme `str.capitalize()`, donc `APIKey`
   devient `Apikey` et `X-Api-Key` devient `X-api-key`. C'est cette forme-là qui
   part sur le fil. Sans conséquence fonctionnelle : les noms d'en-tête HTTP
   sont insensibles à la casse, et la passerelle du bac à sable les traite à
   l'identique.
2. **En Python 3.14, `Request.get_header` est devenu une correspondance
   exacte.** `get_header("APIKey")` retourne donc `None` alors que l'en-tête est
   bien présent sous `Apikey`. Le piège est silencieux parce que les en-têtes
   déjà écrits dans la forme `capitalize()`, `Authorization` en tête, continuent
   de répondre : les tests existants du canal restaient verts, et seuls les
   nouveaux noms en casse mixte échouaient.

**Pourquoi :** un test qui interroge un objet de transport mesure ce que cet
objet a bien voulu conserver, pas ce qui part sur le réseau. Ici il affirmait
une orthographe, là où la propriété qui compte est « l'en-tête est envoyé avec
cette valeur ». La formulation trop précise a rendu le test dépendant d'un
détail d'implémentation de la bibliothèque standard, qui a changé de version en
version.

**Comment appliquer :** asserter un en-tête sortant par une recherche
insensible à la casse (helper `_sent_header` de `tests/unit/test_api_library.py`)
et jamais par `Request.get_header` avec le nom d'origine. Plus généralement,
formuler l'assertion sur la propriété observable côté serveur, pas sur la
représentation intermédiaire. Voir aussi
[[gardes-qui-ne-peuvent-pas-echouer]].
