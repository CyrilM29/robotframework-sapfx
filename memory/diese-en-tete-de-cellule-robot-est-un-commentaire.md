# Un dièse en tête de valeur Robot est un commentaire, et le dry run ne le voit pas

**2026-08-24, génération d'une campagne sur un launchpad Fiori servi par un
serveur ABAP.** Le page object stockait les sélecteurs CSS de la page de
connexion sous leur forme la plus naturelle :

```robotframework
${LOGIN_FORM}      #LOGIN_FORM
${LOGIN_SUBMIT}    #LOGIN_LINK
```

Ces deux variables valent la **chaîne vide**. En Robot Framework, une cellule
qui commence par `#` est un commentaire : le nom est bien défini, sa valeur est
vide, et rien n'est signalé. Le même caractère au MILIEU d'une valeur, lui, ne
pose aucun problème (les fonctions JavaScript du même fichier contiennent
`'#' + intent` et `replace(/^#/, '')` sans dommage) : le piège tient à la
position dans la cellule, pas au caractère.

**Ce que ça coûte.** Le `robot --dryrun` passe : une chaîne vide reste une
chaîne, et la résolution de mots-clés est parfaite. Le garde de conventions
passe aussi. Le premier run LIVE, lui, a échoué en cascade sur les 19 tests,
avec un message qui ne nomme jamais la cause :

```
Could not click dom {'css': ''} after retries.
Last error: TimeoutError: locator.click: Timeout 180000ms exceeded.
```

La suite du run est pire que l'échec initial : l'authentification n'ayant pas
eu lieu, tous les tests suivants ont échoué sur « aucun contrôle UI5 ne
correspond », c'est-à-dire sur le symptôme d'une dérive de localisateur. Le
diagnostic naturel (les identifiants du shell ont changé) est faux, et il est
attirant.

**Comment appliquer.** Écrire les identifiants en sélecteur d'ATTRIBUT plutôt
qu'avec un dièse : `[id="LOGIN_FORM"]`. C'est du CSS strictement équivalent,
sans caractère d'échappement à retenir (`\#LOGIN_FORM` marche aussi, mais se
perd à la première recopie). Et se souvenir que l'échec d'un run live sur un
sélecteur VIDE se lit dans le message : `{'css': ''}` était écrit noir sur
blanc dès la première ligne.

**Second enseignement du même run :** le budget d'attente du navigateur avait
été réglé sur celui du premier chargement d'un système froid (180 s). Appliqué
à toutes les opérations d'élément, il a fait durer chaque échec trois minutes,
et une campagne rouge devient illisible avant d'être diagnostiquée. Séparer les
deux budgets : celui du boot, passé explicitement aux attentes qui en ont
besoin, et celui des éléments, court.
