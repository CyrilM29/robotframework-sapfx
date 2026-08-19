# Trois gardes verts qui ne pouvaient pas échouer

**2026-08-19, revue de code de `integrations/`.** Trois tests écrits pour
protéger une propriété la certifiaient sans jamais pouvoir la contredire. Tous
les trois étaient verts, et deux venaient d'être ajoutés PAR la correction du
défaut qu'ils étaient censés verrouiller.

1. **`hasattr` sur une sous-classe de `Protocol`.** Le contrat de state
   provider de rf-mcp est un `typing.Protocol` qui DÉCLARE ses méthodes avec un
   corps `...`. Toute sous-classe explicite les hérite, donc
   `hasattr(provider, "get_application_state")` vaut **toujours** `True` :
   l'assertion « la capacité déclarée correspond à ce qui est implémenté »
   dégénérait en `True is True`. Pire, elle s'inversait sur le cas honnête : un
   futur provider qui déclarerait franchement `supports_application_state=False`
   aurait fait ROUGIR le test, et la « correction » aurait été de mentir dans le
   drapeau. La question qui a du sens :
   `type(provider).get_application_state is not Protocol.get_application_state`.
2. **Un garde anti-duplication qui cherche un NOM.** Après extraction d'un
   helper partagé, le test vérifiait `"def _structured" not in source` dans les
   trois modules. Il ne voyait ni une copie renommée, ni la copie **inline**
   (sans `def`) qui survivait justement dans le troisième plugin, jamais migré.
   Vert, alors que la propriété annoncée était fausse au moment même où le test
   était écrit.
3. **Une doublure posée dans le mauvais espace de noms.** Le code partagé ayant
   déménagé, `monkeypatch` du nom dans le module appelant ne remplaçait plus
   rien : le VRAI appel s'exécutait et échouait faute de contexte, ce qui
   produisait exactement les clés d'erreur attendues. Signe mesurable : ce test
   durait 1,53 s quand tous ses voisins tenaient sous 0,04 s, et il construisait
   silencieusement une vraie session dans le process de test.

**Pourquoi :** un garde vert transforme « personne n'a vérifié » en « la CI dit
que c'est bon », ce qui est pire que pas de test : il éteint le réflexe de
regarder. Les trois ont la même racine, une assertion sur un PROXY de la
propriété (présence d'un attribut, présence d'un nom dans le source, forme du
résultat) au lieu de la propriété elle-même.

**Comment appliquer :** pour tout garde, écrire d'abord la contre-épreuve, le
cas qui DOIT le faire échouer, et la garder dans la suite. Se méfier des
assertions sur du texte de source, et vérifier qu'une doublure a réellement
joué (un temps d'exécution anormal est un indice fiable). Voir aussi
[[rfmcp-retour-none-devient-ok]] et [[replay-recorder-vert-et-faux]].
