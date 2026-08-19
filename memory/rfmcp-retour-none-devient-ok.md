# rf-mcp remplace un retour `None` par la chaîne « OK »

**2026-08-19, revue de code de `integrations/`.** Le gestionnaire de contexte
RF natif de rf-mcp construit ses réponses de succès ainsi (deux sites de retour,
identiques) :

```python
return {"success": True, "result": result,
        "output": str(result) if result is not None else "OK", ...}
```

Autrement dit, un keyword qui ne retourne rien produit `result = None` **et**
`output = "OK"`. Le pont contexte-RF du dépôt lisait `result`, puis retombait
sur `output` quand `result` valait `None` : il récupérait donc « OK » et son
garde « sortie vide » était **inatteignable**. Une section d'état applicatif
indisponible arrivait à l'agent servie comme une valeur, sous la forme d'un
franc `"OK"`, indistinguable d'une vraie réponse.

Le test unitaire qui prétendait couvrir ce garde assertait sur
`{"result": None, "output": None}`, une forme que rf-mcp **n'émet jamais** :
il verrouillait un garde mort en production. Corrigé le même jour :
`result` fait foi dès que la clé est présente, le repli sur `output` ne sert
qu'aux réponses sans cette clé et y neutralise la sentinelle.

**Pourquoi :** on ne peut pas déduire le contrat d'un service tiers de ses
noms de clés. Ici deux clés cohérentes (`result` et sa forme texte) cachaient
une substitution silencieuse, et le repli « si l'un est vide, prends l'autre »,
qui paraît prudent, retournait une valeur inventée par la couche de transport.

**Comment appliquer :** quand une doublure de test décrit un service tiers,
vérifier la forme réelle DANS SA SOURCE avant de la figer, et se méfier des
replis en cascade entre deux champs qu'un producteur remplit ensemble. Voir
aussi [[gardes-qui-ne-peuvent-pas-echouer]].
