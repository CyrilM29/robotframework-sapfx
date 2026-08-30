# Promouvoir une capacité peut tuer, en silence, la surface qu'un agent répare

Observation datée : 2026-08-29.

En promouvant les primitives d'écran SE16 de la couche resources vers la
bibliothèque (convention #12), la cible du harnais d'éval en aveugle du
sap-healer allait disparaître : le scénario canonique injectait une dérive sur
`${SE16_COUNT_BUTTON}`, une variable de `resources/ecc_keywords.resource` que
la promotion rendait morte.

**Le point de conception, valable au-delà de ce cas** : le healer répare la
couche `resources/`, JAMAIS la bibliothèque. Chaque promotion déplace donc
quelque chose hors de son atteinte. Ce n'est pas un argument contre la
promotion (le dépôt a tranché depuis longtemps : les ids d'écrans SAP
STANDARD appartiennent à la bibliothèque, au même titre que le popup F4 ou
les champs de login), mais c'est un effet de bord à regarder à chaque fois.
Ce qui doit rester dans `resources/` est ce qui VARIE d'un site, d'une table
ou d'un profil à l'autre : c'est là qu'une dérive se produit vraiment, et
c'est donc là que le healing a un sens.

**Ce qui a évité le silence** : un test unitaire vérifiait que la cible du
scénario existe EXACTEMENT une fois dans la vraie resource
(`test_the_default_scenario_matches_the_real_repo_resource`). Sans lui, le
harnais aurait continué à « passer » en injectant dans le vide, et l'éval du
healer serait devenue verte sans rien éprouver : le pire mode de panne d'un
filet de régression, celui qui ne se voit pas. Un harnais qui pointe une
ressource externe doit toujours porter ce garde de vivacité.

Le scénario a été déplacé vers `se16-table-field`
(`ctxtDATABROWSE-TABLENAME` -> `ctxtDATABROWSE-TABNAME`) : il reste dans la
resource, il est sur le chemin de la suite d'éval, et sa proximité avec
l'original donne au scoring du healer une vraie matière, ce qu'un bouton
renuméroté offrait moins.

Corollaire de nommage rencontré au passage : Robot dérive « Use Alv Grid In
Data Browser » d'une méthode `use_alv_grid_in_data_browser`. Le matching
Robot ignore la casse, donc rien ne casse, mais la documentation publiée
citerait un sigle abîmé : `@keyword("Use ALV Grid In Data Browser")` fixe le
nom exposé. À faire pour tout keyword dont le nom porte un acronyme.
