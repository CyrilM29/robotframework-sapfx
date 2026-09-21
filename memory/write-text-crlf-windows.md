---
name: write-text-crlf-windows
description: Sous Windows, Path.write_text convertit les fins de ligne en CRLF ; une preuve épinglée par empreinte est alors refusée par le test du contrat d'agents alors que le vérificateur de sidecars, lui, la validait ; ouvrir avec newline explicite et relancer pytest
type: projet
date: 2026-09-21
---

# `Path.write_text` écrit du CRLF sous Windows, et une preuve épinglée le refuse

**Relevé le 2026-09-21**, en produisant la preuve de run et le sidecar de
handoff d'une campagne.

## Le fait

`pathlib.Path.write_text` ouvre en mode texte avec la traduction de fins de
ligne de la plateforme : sous Windows, chaque `\n` devient `\r\n`. Le test
unitaire qui vérifie les sidecars refuse une preuve épinglée portant du CRLF
(la même preuve aurait deux empreintes selon le poste qui l'écrit). Le sidecar
lui-même passait `agent_contract.py`, qui ne regarde que la structure et les
empreintes : seul `pytest` l'a vu.

## Ce qu'on en fait

- Écrire les artefacts épinglés avec
  `open(path, "w", encoding="utf-8", newline="\n")`, jamais `write_text`.
- Après toute réécriture d'une preuve, rafraîchir les empreintes du sidecar
  qui la référence, puis relancer `pytest`, et pas seulement
  `agent_contract.py`.
