# Un serveur peut compresser une réponse qu'on ne lui a pas demandé de compresser

**2026-08-22, premier run live du canal API contre le bac à sable SAP Business
Accelerator Hub.** Trois scénarios sur quatre au vert du premier coup. Le
quatrième échouait ainsi :

```
Document $metadata illisible en XML (not well-formed (invalid token):
line 1, column 0) : le chemin pointe-t-il bien la racine du service ?
(statut 200)
```

Le message est bien construit, il nomme le statut, l'URL et une piste. Et il
accuse le mauvais coupable. Une sonde de trois lignes sur la vraie URL a donné
la réponse en une seconde :

```
Content-Type     : application/xml
Content-Encoding : gzip
30 premiers octets: b'\x1f\x8b\x08\x00...'
```

`1f 8b` est la signature gzip. Le document était parfaitement valide : il
arrivait **compressé**, et les octets compressés atteignaient le parseur XML.
Or le client n'envoie **aucun** `Accept-Encoding` : la compression n'a jamais
été négociée, le serveur l'applique de lui-même.

Deux raisons pour lesquelles le trou avait survécu à deux cibles live :
ce serveur ne comprime que la voie XML, donc toutes les lectures JSON
passaient ; et ni la Gateway A4H ni CAP ne compriment quoi que ce soit.

**Pourquoi :** « line 1, column 0 » est la signature d'un corps binaire, pas
d'un document mal formé, et un parseur ne peut pas le savoir. Un message
d'erreur soigneusement rédigé garde le point de vue de la couche qui le rédige,
donc il désigne le document quand le fautif est le transport. Un statut 200
avec un corps illisible doit faire regarder les en-têtes de réponse AVANT le
contenu.

**Comment appliquer :** décompression posée à la frontière du transport, pour
tous les corps lus (charges utiles, extraits d'erreur, sondes de préflight,
endpoint de token), jamais dans un keyword particulier. Un encodage qu'on ne
sait pas défaire laisse le corps intact plutôt que de lever : le diagnostic du
niveau au-dessus reste meilleur qu'une exception de `zlib`. Et devant un 200
au corps incompréhensible, sonder l'URL réelle avant de suspecter le chemin.
Voir aussi [[canal-api-odata-v4-pieges]] et
[[angle-mort-canal-teste-en-indirect]] : une cible live de plus révèle ce que
les précédentes absorbaient.
