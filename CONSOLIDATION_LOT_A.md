# ORBITE — consolidation, lot A

Date : 2026-10-30. Statut : implémenté, validation partielle ; pas de validation de production.

## Références et périmètre

- Dépôt : `jeromeltge-ctrl/ORBITE-VoC-Audika-V1`.
- Branche de travail : `consolidation-orbite`.
- Source validée : `orb022-gestion-imports-google`, commit `2943db315edf2ee4007bf0f035985583951da4f7`.
- Main conservée : `7c0d0a96a8106ce61b2342874c685e383f1bf7b5`.
- Code testé localement : arbre du commit `4439e5f37e89980bf15b871d7804b47c234f3d19`.
- Workflow étendu au push de la branche de travail : `982355661a22d0d8d6a0ad339a158b0eaad77259`.
- Livraison : PR #1, en brouillon, sans fusion dans main.
- PR technique #2 : intégration de l'ascendance de main dans la branche de travail pour résoudre un conflit ajout/ajout sur `import_deletion.py`. Commit de réconciliation `4439e5f37e89980bf15b871d7804b47c234f3d19`, aucun changement de fichier par rapport à son premier parent. Main n'a pas été modifiée.

Lot A uniquement. Aucun développement des lots B à E, aucun déploiement, aucune base métier utilisée ou modifiée pendant les tests. Une compilation ne vaut pas recette métier.

## Inventaire et analyse d'impact

Architecture observée : React/TypeScript → `electron/preload.cjs` → `electron/main.cjs` → protocole JSON ligne par ligne → `orbite_backend.run` → modules Python.

| Module | Rôle / dépendances |
| --- | --- |
| `orbite_data.py` | SQLite ORBITE, imports Excel NPS/référentiel, filtres, publication et verbatims |
| `import_deletion.py` | Traçabilité, inventaire, sauvegarde et suppression NPS |
| `nps_analytics.py` | Calculs NPS et période précédente, non modifiés |
| `question_analytics.py`, `survey_library.py` | Questions additionnelles, versions et résultats, non modifiés |
| `network_analytics.py` | Lecture réseau NPS, non modifiée |
| `ereputation_bridge.py`, `engine.py` | Adaptateur et moteur Google historique, non modifiés |
| `shared_reference.py`, `google_deletion.py` | Corrections existantes de la branche source, conservées |
| `interactive_export.py`, `report.py`, `modele_consolide2.xlsx` | Exports et modèle Excel historiques, non modifiés |
| `src/main.tsx` | Navigation et chargement des imports, intégration du composant NPS ciblé |
| `NpsDashboard`, `SurveyLibrary`, `NetworkDashboard`, `GoogleFusion`, `GoogleDataManagement` | Composants existants conservés |

Stockages distincts maintenus : `orbite.sqlite` et `google.sqlite`.

Tables NPS concernées : `nps`, `imports`, `tracked_nps_imports`, `import_deletion_log`. Le marqueur de suivi et la colonne `nps.import_id` existaient déjà dans la branche source validée. La migration additive existante est conservée ; aucune reconstruction ni réinitialisation automatique.

Tables protégées pendant suppression/réinitialisation NPS : `centres`, `settings`, bibliothèque des enquêtes et questions ; fichier Google entier. Les vues NPS, questions et réseau doivent refléter les lignes restantes après rafraîchissement, sans modification des formules métier.

L'inventaire ne constitue pas un audit fonctionnel exhaustif des lots B à E. Le modèle Excel n'a pas été analysé ou modifié pendant ce lot. Les documents `ARCHITECTURE.md`, `FUNCTIONAL_REQUIREMENTS.md`, `BUSINESS_RULES.md`, `CHANGELOG.md`, `TEST_PLAN.md`, `KNOWN_ISSUES.md` n'étaient pas présents à la racine examinée ; leur création complète reste à proposer séparément.

## Anomalies traitées

| Identifiant | Priorité | Constat confirmé | Traitement |
| --- | --- | --- | --- |
| A-001 | P2 | Le backend de la branche source expose la suppression NPS mais le preload ne l'autorise pas | Autorisation ciblée des 3 méthodes NPS ; tests du pont |
| A-002 | P2 | Métadonnées import incomplètes côté client | `import_id`, `affected_rows`, `can_delete`, `deletion_reason` renvoyés |
| A-003 | P2 | Absence d'écran de réinitialisation historique raccordé | Composant dédié, périmètre global visible, saisie textuelle et confirmation |
| A-004 | P2 | Contrôle, sauvegarde et suppression non protégés par un verrou commun ; sauvegarde non vérifiée | Transaction réservant l'écriture, sauvegarde par lecteur distinct, contrôle d'intégrité, audit atomique |
| A-005 | P2 | Deux fixtures historiques insèrent 11 valeurs sans colonnes nommées dans une table enrichie d'import_id | Colonnes explicites ; assertions historiques inchangées |

Le risque de course d'A-004 est une analyse de risque, pas une affirmation de perte de données observée en production. Aucun incident métier réel n'a été reproduit sur des données de production.

## Contrats et garanties implémentés

- `importNps` conserve les clés historiques `added`, `ignored`, `outside_reference` et ajoute `import_id`, `affected_rows`, `can_delete`, `deletion_reason`.
- Chaque tentative d'import reçoit son propre ID AUTOINCREMENT, persistant. Un réimport identique ajoute 0 ligne et ne réaffecte jamais les réponses à un nouveau lot.
- Le lot, son marqueur de provenance et les lignes sont validés dans une même transaction. Une exception annule l'ensemble.
- `imports` conserve `id` et ajoute les métadonnées de suppression. L'inventaire ne masque plus les lots au-delà des 100 premiers imports.
- `affected_rows` est le nombre réellement rattaché à l'ID, pas une supposition tirée du nom de fichier. Pour un ancien lot sans lien, ce nombre peut être 0 alors que des lignes historiques existent : `can_delete=false` et le motif restent déterminants.
- `deleteImport` exige un ID entier positif représentable sans perte en JavaScript et la confirmation exacte `SUPPRIMER IMPORT NPS <id>`, vérifiée dans Electron et dans le backend.
- Un lot non suivi, non NPS ou dont le nombre de lignes diffère du nombre ajouté est refusé.
- Avant toute suppression effective : `BEGIN IMMEDIATE`, contrôle sous verrou, sauvegarde SQLite par connexion de lecture distincte, `PRAGMA integrity_check`, puis suppression des lignes, métadonnées et marqueur avec journal dans la même transaction.
- Un échec de sauvegarde ou de journalisation ne valide aucune suppression. Une sauvegarde créée avant un échec ultérieur est conservée.
- `legacyImportStatus` expose `legacy_rows` et `legacy_imports`.
- `resetLegacyNps` exige `REINITIALISER ANCIENS NPS`. L'interface affiche le nombre de lignes et d'imports et demande une confirmation supplémentaire.
- La réinitialisation est globale et indépendante des filtres. Elle cible uniquement les lignes sans association à un lot NPS suivi : ID NULL, orphelin ou sans marqueur de suivi. Les lots suivis dont les effectifs sont incohérents restent protégés et nécessitent un diagnostic séparé.
- Les noms de fichiers ne servent jamais à décider des suppressions. Le nom temporaire `import.xlsx` utilisé par le staging Electron existant n'est pas corrigé dans ce lot : l'ID et la date distinguent les lots.
- Les fonctions internes Python historiques restent disponibles. Seul l'appel destructif RPC impose désormais la confirmation supplémentaire.

## Fichiers livrés — par rapport à la branche source validée

Modifiés (7) :
1. `backend/orbite_data.py`
2. `backend/import_deletion.py`
3. `backend/orbite_backend.py`
4. `backend/test_lots012.py`
5. `backend/test_network.py`
6. `electron/preload.cjs`
7. `src/main.tsx`

Ajoutés (8, dont 2 repris sans modification depuis main) :
1. `.github/workflows/consolidation.yml`
2. `backend/test_consolidation_a.py`
3. `backend/test_consolidation_a_ipc.py`
4. `backend/test_delete_import.py` — repris de main
5. `backend/test_reset_legacy.py` — repris de main
6. `electron/preload.test.cjs`
7. `src/NpsImportManagement.tsx`
8. `CONSOLIDATION_LOT_A.md`

Supprimés : aucun.

Les fichiers Google/shared_reference apparaissant dans la comparaison avec main sont hérités de la branche source autorisée, pas développés dans ce lot. Les sources complètes sont disponibles sur la branche et via l'archive GitHub de cette branche.

## Tests réellement exécutés localement

Sources récupérées depuis les résultats GitHub ; empreintes blob vérifiées contre le dépôt avant exploitation des résultats. Tests sur bases temporaires exclusivement. Aucune dépendance métier simulée pour les 18 tests Python ci-dessous.

Commande Python, depuis backend :

```text
python -m unittest test_consolidation_a test_delete_import test_reset_legacy test_google_deletion -v
```

Résultat : **18 tests réussis, 0 échec** :
- 15 nouveaux tests lot A : contrat et persistance du lot ; réimport/doublons ; fichiers recouvrants ; refus historique/référentiel ; sauvegarde avant suppression et journal ; échec de sauvegarde ; échec de journalisation ; rollback d'import ; WAL et verrou concurrent ; réinitialisation/idempotence ; provenance orpheline ; lot suivi incohérent ; visibilité de 101 lots ; lignes invalides/hors référentiel ; confirmations et IDs.
- 2 tests historiques repris de main : suppression ciblée et réinitialisation préservant les nouveaux lots et le référentiel.
- 1 test historique de gestion Google conservé.
- Les 15 tests lot A vérifient chacun la conservation de l'empreinte du fichier Google et des centres, paramètres et enquêtes témoins.

Commande Node :

```text
OPENSSL_CONF=/dev/null node --test electron/preload.test.cjs
```

Résultat : **6 tests réussis, 0 échec**. Tests de contrats du preload avec doubles IPC, pas une exécution de l'interface Electron. Le premier lancement Node a échoué avant exécution sur un fichier de configuration OpenSSL inaccessible ; la reprise utilise la configuration par défaut sans ce fichier, sans connexion réseau.

Autres contrôles réussis : compilation syntaxique des fichiers Python de la copie de validation disponible et `node --check electron/preload.cjs`.

## Contrôles non encore validés

- Suite Python exhaustive : non exécutée localement ; les 18 tests ci-dessus sont un sous-ensemble ciblé.
- Les 3 nouveaux tests `test_consolidation_a_ipc.py` (processus Python réel puis EXE) : non exécutés localement à la rédaction de ce rapport.
- TypeScript/React complet, PyInstaller, packaging Electron Windows : non exécutés localement ; outils npm/tsc non disponibles dans l'environnement de validation utilisé.
- Recette graphique : non exécutée.
- Test Google sur données métier réelles : données non fournies ; ne pas déclarer ce test réussi.
- GitHub Actions : workflow de validation ajouté et déclenchement prévu sur push/PR de consolidation, sans publication. Aucun résultat de check run n'était remonté lors de la rédaction ; la présence du workflow n'est pas une preuve d'exécution.

Le workflow Windows existant `windows.yml` est inchangé. Il peut être lancé manuellement depuis GitHub Actions en sélectionnant `consolidation-orbite`. Le workflow de consolidation ajoute les contrôles preload et IPC packagé, en lecture seule sur le dépôt et sans déploiement.

## Critères de clôture / risques résiduels

Le lot n'est pas déclaré entièrement validé : attendre les tests IPC, le contrôle TypeScript, le build Windows et la recette des confirmations/rafraîchissements sur une copie des données. Aucun passage au lot B avant validation des tests du lot A par Jérôme.

Les données métier NPS invalides, correspondances de campagnes, taux de réponse et KPI Google ne sont pas réinterprétés ici. Les suppressions sont des opérations locales durables : les fichiers de sauvegarde doivent rester accessibles et bénéficier des protections d'accès du dossier utilisateur.

## Retour arrière

Avant recette, sauvegarder séparément les deux bases et conserver l'ancien exécutable. Ne pas utiliser les données de production pour tester les suppressions.

Retour du code : utiliser la référence source autorisée, sans prétendre qu'elle constitue une version stable validée. Aucune version stable officiellement validée n'a été identifiée pendant ce lot.

Retour des données : arrêt complet de l'application et du sidecar, conservation de l'état courant, contrôle de la sauvegarde SQLite, restauration supervisée après autorisation distincte. Une sauvegarde ORBITE complète restaure aussi les autres tables ORBITE à l'instant de la sauvegarde : ne jamais l'écraser automatiquement sur une base ayant reçu de nouveaux imports. Une restauration du code ne restaure pas les données. Ne jamais remplacer `google.sqlite` pour annuler une suppression NPS.
