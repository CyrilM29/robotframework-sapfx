# memory/ — mémoire projet des assistants IA

Fiches de travail persistantes des assistants IA (Claude Code, GitHub Copilot,
Codex…) travaillant sur ce dépôt. Rédigées en français, la langue de travail
(hors contrat bilingue, comme `specs/` — exemption dans
`scripts/check_bilingual_docs.py`).

**Cette mémoire est committée et part avec le dépôt : tout son contenu doit
être publiable.** Règles non négociables :

1. **Anonymisé** : aucune donnée personnelle (nom, e-mail, compte), aucun
   chemin machine (`C:\Users\…`, `E:\…`), aucune URL privée, aucun secret.
   Ce qui est personnel, lié au poste ou inter-projets va dans la base de
   mémoire privée de l'utilisateur, jamais ici.
2. **Une fiche = un fait durable du projet** : leçon de débogage coûteuse,
   décision avec son contexte, procédure d'environnement générique. Pas de
   journal de session, pas de duplication de ce que documentent déjà
   CLAUDE.md, les docs ou le git.
3. **Dates absolues** ; une fiche est une observation datée, pas un état
   vivant — vérifier avant d'affirmer.
4. **`MEMORY.md` est l'index** : une ligne par fiche, mis à jour dans la même
   opération que toute création/suppression. Mettre à jour plutôt que
   dupliquer ; supprimer ce qui est devenu faux.

Format d'une fiche :

```markdown
---
name: slug-kebab-case
description: résumé en une ligne — décide si on ouvre la fiche
type: projet | reference | recherche
date: AAAA-MM-JJ
---

Le fait. **Pourquoi :** le contexte. **Comment appliquer :** le geste attendu.
```
