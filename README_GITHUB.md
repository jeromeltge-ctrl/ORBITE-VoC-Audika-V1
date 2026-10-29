# ORBITE VoC — Paquets 0, 1 et 2 (branche de recette)

## Important
Les trois archives sont **complémentaires**. Le paquet 0 déclare les contrats NPS et Questions ; il ne doit pas être compilé seul sans les modules des paquets 1 et 2. Installer **0, puis 1, puis 2**, faire un seul commit, puis lancer GitHub Actions.

**Sauvegarder le dépôt, l'ancien EXE et la base SQLite avant toute modification.** Ne pas supprimer les données locales. Aucune migration de base n'est prévue.

### Paquet 0 — Stabilisation moteur et contrats
Remplacer : `backend/orbite_backend.py`, `backend/orbite_data.py`, `electron/main.cjs`, `electron/preload.cjs`, `.github/workflows/windows.yml`.
Ajouter : `backend/smoke_sidecar.py`.
- Contrats `health`, `npsDashboard`, `questionAnalysis`, `questionHistory`, `questionProfile`, `questionResults`.
- Journal des erreurs du moteur dans le dossier utilisateur Electron (`orbite-backend.log`).
- Filtre de campagne corrigé sur `appt_type` (source `custom_appointment_type`).
- Workflow avec test du sidecar Python compilé.

### Paquet 1 — NPS
Ajouter : `backend/nps_analytics.py`, `src/NpsDashboard.tsx`.
- NPS, taux de réponse, volumes, distribution, campagnes OPPS avec/sans PM et total, courbe mensuelle RatingTime.
- Comparaison à la période précédente de même durée lorsque les deux dates sont renseignées.
- Les familles non documentées restent nommées comme dans les données ; pas de mapping inventé TSR/3,8 ans.

### Paquet 2 — Questions additionnelles
Ajouter : `backend/question_analytics.py`, `src/SurveyLibrary.tsx`, `src/lot012.css`, `backend/test_lots012.py`.
Remplacer : `src/main.tsx`.
- Lecture de `Answer1` à `Answer5`, analyse des réponses et recherche.
- Bibliothèque existante (`survey_library.py`) préservée, fiches, versions, comparaisons.
- Aucun libellé historique inventé lorsque les imports ne le contiennent pas.
- Intégration des deux composants dans la navigation.

## Fichiers à conserver
Conserver `backend/survey_library.py`, `src/style.css`, `src/types.d.ts`, `package.json`, les modèles et moteurs Google, tous les fichiers non listés comme remplacés.

## Vérifications effectuées
- Test Python de contrat sur base SQLite **synthétique** : health, NPS, questions, filtres : OK.
- Syntaxe Python, Electron : OK.
- Analyse syntaxique JSX/TSX : OK (ce n'est pas un contrôle de typage complet).
- Build Windows, lancement de l'EXE et recette métier sur données réelles : **non exécutés ici**.

## Installation
1. Créer une branche `stabilisation-nps-questions` depuis la version source de référence.
2. Superposer les trois ZIP **dans l'ordre 0 → 1 → 2**, à la racine du dépôt.
3. Commit ; ne pas toucher à `main`.
4. Actions → ORBITE VoC Windows Electron → Run workflow → branche `stabilisation-nps-questions`.
5. Vérifier le nouveau test `Verify compiled backend contracts`, puis le build React/Electron.
6. Sur l'EXE de recette : contrôler la Vue d'ensemble, les Campagnes NPS, les Questions additionnelles, les filtres région/secteur, puis les exports et imports existants.
7. Si le moteur s'arrête, consulter `orbite-backend.log` dans le dossier des données utilisateur Electron.

## Limites métier à valider
- Le taux de réponse sur une plage de dates utilise les enregistrements dont la date effective est RatingTime pour une réponse notée, SurveySendTime sinon (comportement de filtrage historique conservé). Ce n'est pas automatiquement un taux par cohorte d'envoi.
- Les correspondances exactes des sous-campagnes OPPS, TSR et 3,8 ans nécessitent validation sur tes libellés réels.
- L'analyse des questions ne rattache pas automatiquement les réponses sans libellé à une version officielle d'enquête.
