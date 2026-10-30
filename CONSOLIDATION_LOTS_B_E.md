# Consolidation ORBITE — lots B à E

Date : 2026-10-30. Dépôt : `jeromeltge-ctrl/ORBITE-VoC-Audika-V1`. Branche : `consolidation-orbite`. PR de livraison : #1, brouillon.

**Statut : corrections commitées et tests Python exécutés ; stabilisation finale NON validée.** Les lots D et E ne sont pas clôturés. Ne pas présenter cette branche comme une version stable ou prête pour la production.

## Autorisation et référence

Jérôme a autorisé le 2026-10-30 à 10:03 UTC l'enchaînement des lots A à E sans accord intermédiaire, avec exécution des contrôles disponibles et blocage de la livraison finale tant que les contrôles indispensables ne sont pas validés. Cette autorisation remplace la condition d'accord entre lots du rapport A, pas l'obligation de tests. Aucune fusion vers main ni production autorisée.

- Point de départ de cette intervention : `2b2eee9dae613bebe42ba73f6e1374587102179d`.
- Sources Python testées : `34396d145d22ba717ed9c6ff7bdc8bd4b6e23d2a`.
- Workflow Windows renforcé ensuite : `7ba9a8368653fe61ae999927fd941b952c00aa6e`.
- Main conservée : `7c0d0a96a8106ce61b2342874c685e383f1bf7b5`.
- Aucune version stable explicitement validée n'est identifiée ; le dernier commit n'est pas assimilé à une version stable.

## B — consolidation NPS

### Diagnostic / impacts

Les calculs `nps_analytics.metrics` tronquaient les notes via `int()` et pouvaient échouer sur des chaînes invalides. `orbite_data.metrics` utilisait une autre validation, d'où un risque de désaccord entre vue d'ensemble, campagnes et réseau. Le taux de réponse utilisait directement le nombre d'enregistrements comme dénominateur, sans preuve d'une cohorte d'envoi fiable.

Fichiers directs : `backend/nps_analytics.py`, `backend/orbite_data.py`, `src/NpsDashboard.tsx`. Dépendances : vue d'ensemble, campagnes, timeline, réseau, filtres et questions. Aucune migration de données existantes.

### Corrections

- Validation commune : notes entières finies entre 0 et 10 ; booléens, fractions, valeurs hors intervalle et chaînes invalides exclus.
- Détracteurs 0–6, passifs 7–8, promoteurs 9–10. NPS = 100 × (promoteurs − détracteurs) / réponses valides, jamais moyenne des NPS des centres.
- `orbite_data.metrics` utilise le même calcul que le dashboard NPS et le réseau.
- Les alias existants `avec prescription` et `sans prescription` sont conservés ; `CampaignName` ne sert pas de mapping métier. Aucun nouvel alias commercial inventé.
- Lorsque des OPPS existent dans la période courante ou comparée, les vues avec PM, sans PM et total sont conservées ; une sous-campagne absente affiche 0 réponse et NPS N/C. Le total est recalculé sur les réponses, pas sur les scores agrégés.
- Deux modes : `previous_period` (même durée inclusive), `year_over_year` (N/N-1). Les dates courantes et comparées sont affichées.
- Convention visible pour le 29 février : rapprochement au 28 février lorsque l'année précédente n'est pas bissextile.
- Taux de réponse **N/C** : aucun dénominateur fiable n'est disponible dans le schéma importé. Les clés historiques de compte sont conservées pour compatibilité mais ne constituent pas une validation métier des sollicitations. Explication visible dans les écrans.
- Normalisation des bornes et dates de nouveaux imports ; filtrage des dates historiques interprétables sans réécriture de la base. Les valeurs de date non interprétables sont conservées mais ne passent pas un filtre de dates.

### Tests

11 tests du lot B réussis : signes du NPS, bornes 0–10, invalides, absence de réponses, pondération nationale/OPPS, sous-campagne absente, dénominateur non établi, période précédente, N/N-1 et bissextile, périodes invalides, campagne uniquement présente dans la période précédente.

Test IPC réel supplémentaire : import NPS, comparaison N/N-1 avec écart de 200 points sur données synthétiques (+100 contre −100), période précédente, questions, réseau et export CSV.

### Risques / acceptation restante

La baisse du nombre de réponses valides en présence de notes historiques invalides est intentionnelle. Le taux de réponse n'est plus affiché comme un pourcentage établi ; un futur rétablissement exige une définition métier et des données de sollicitations fiables. La recette graphique et TypeScript restent non exécutées.

## C — cohérence NPS / Google

### Diagnostic / impacts

Les dates Google par défaut différaient entre la vue d'ensemble et `ereputation_bridge.summary` (périodes codées en dur dans ce dernier et dans React). Les tableaux de régions pouvaient ignorer le filtre sectoriel. Une somme de données absentes pouvait être présentée comme zéro. Le routeur déclenchait une synchronisation du référentiel NPS avant de valider l'import Google, ce qui bloquait une installation Google seule.

Fichiers directs : `backend/google_view.py`, `backend/ereputation_bridge.py`, `backend/orbite_backend.py`, `src/GoogleFusion.tsx`, `src/main.tsx`. Dépendances : moteur historique, filtres, vue exécutive et exports.

### Corrections

- `engine.py` reste inchangé. `google_view.py` adapte ses résultats et expose leur couverture ; aucune fusion de SQLite.
- Lectures Google en mode SQLite `mode=ro`, sans création de base vide par simple consultation.
- Même résolution de période pour les KPI Google dédiés, la vue exécutive et l'export : bornes explicites sinon janvier à la dernière période importée. Dates de comparaison N-1 exposées.
- Sources Google mensuelles : une borne journalière non alignée sur un mois est explicitement signalée ; les mois contenant les bornes sont utilisés en entier. Aucun prorata journalier inventé.
- Intersection des filtres région/secteur dans les agrégats et tableaux. Union des choix géographiques NPS et Google, sans remapper physiquement les centres.
- Volume inconnu = `None` / N/C ; zéro connu = 0. En cas de couverture partielle, les volumes restent identifiés comme **connus**, avec nombre d'observations centre/mois présentes et attendues.
- Évolution des volumes N/N-1 indisponible si les deux périodes ne sont pas complètes ou contiennent des mois provisoires. La note reste la moyenne pondérée du moteur historique à la fin de période ; les nombres de centres avec note sont exposés.
- Indicateur sectoriel principal : nouveaux avis de la période, pas cumul historique.
- Imports Google indépendants du référentiel NPS. La synchronisation existante reste disponible explicitement ; elle n'est plus un effet préalable de `googleImport`. Le comportement existant de `importReference` est conservé.
- Validation stricte de la confirmation Google, formats de dates Uberall normalisés, sauvegarde vérifiée, fermeture du générateur Excel même si l'import échoue.
- Après import Google, rafraîchissement des filtres et KPI principaux. Protection contre les anciennes réponses asynchrones dans l'écran Google.

### Tests

9 tests de l'adaptateur Google réussis : absence de base, Google seul, filtres croisés, zéro/absence, périmètre vide, bornes mensuelles explicites, équivalence avec le moteur sur cas complets, union géographique, cohérence de la vue exécutive.

Scénarios IPC réels réussis : Google seul, réimport historique sans doublons, refus de confirmation/empreinte incorrectes sans mutation, coexistence NPS/Google, source absente dans un périmètre. Tests historiques de mapping, import synthétique et vue d'ensemble réussis.

### Risques / acceptation restante

Google mensuel et NPS journalier n'ont pas la même résolution ; ce fait est affiché, pas masqué. Les référentiels différents ne sont pas considérés identiques : les nombres de centres par source sont distingués. Les tests sur les fichiers métier réels restent ignorés faute de données.

## D — exports

### Diagnostic / impacts

Le builder historique parcourait le référentiel entier pour certaines listes et la feuille détaillée ; des KPI de productivité pouvaient utiliser un nombre de centres national malgré un filtre. Les données détaillées n'étaient pas limitées aux périodes sélectionnées. Des noms contenant des guillemets pouvaient produire des formules incorrectes. La destination était écrite directement sans conservation d'un export préexistant.

Fichiers directs : `backend/export_guard.py`, branche export de `backend/ereputation_bridge.py`. Le code historique `interactive_export.py`, `report.py` et le modèle `modele_consolide2.xlsx` sont conservés, non remplacés par un export simplifié.

### Corrections implémentées

- Copie SQLite temporaire en mémoire, avec référentiel limité au périmètre demandé ; aucune suppression sur la source. Le builder historique travaille sur cette copie.
- Sortie temporaire dans le même dossier que la destination, vérification de réouverture, sauvegarde d'un export précédent, remplacement atomique.
- Refus d'écraser le modèle ou une base, refus des périmètres vides.
- Conservation des feuilles historiques ; adaptation des cellules de sortie pour distinguer l'absence d'observations d'un zéro connu ; guillemets échappés dans les noms de centres.
- Feuille détaillée limitée à N et aux mêmes mois de N-1 dans le périmètre sélectionné.
- Feuille supplémentaire `CONTROLES ORBITE` : périodes, périmètre, totaux, régions, secteurs, centres, volumes connus, note pondérée et couverture. Elle est une photographie calculée à l'export.
- Recalcul des formules demandé à Excel à l'ouverture. Aucune prétention de calcul des formules par openpyxl.

### Tests et limites importantes

3 tests du garde d'export réussis **avec un double du builder historique** : périmètre isolé, conservation de la source et du modèle, sauvegarde de la destination, échec sans écrasement, chemins protégés, structure de la feuille de contrôles et traitement des guillemets.

Le test du **véritable builder avec le modèle original** est présent, mais ignoré localement : récupération du modèle GitHub de 2179836 octets refusée HTTP 403. Son empreinte GitHub reste `0334213bf1b067c3f439c3b194ddc8e66511f761`. Le workflow Windows exige la présence et l'empreinte exacte du modèle avant de lancer la suite.

**Lot D non clôturé.** Le rendu, les graphiques, les cellules fusionnées, les formules et les valeurs après recalcul du véritable classeur restent à vérifier. La feuille de contrôles est figée à la période d'export ; il faut régénérer l'export après changement de période/périmètre. L'utilisation des menus interactifs historiques après génération nécessite une recette spécifique, notamment lorsque la comparaison a été marquée N/C. Les données Uberall sans historique cumulatif suffisant doivent être incluses dans cette recette : l'adaptateur d'écran les lit, mais la compatibilité du builder historique sur ce cas n'est pas établie.

Aucun changement arbitraire du fichier modèle. Aucun résultat Excel métier déclaré conforme sans cette recette.

## E — tests et stabilisation

### Résultats réellement exécutés

Commande exécutée sur une copie vérifiée des sources GitHub, avec bases temporaires synthétiques :

```text
python run_validation.py --output /app/workspace/orbite-validation-results-complete.json
```

Bilan à `2026-10-30T10:11:01.155760+00:00`, Python `3.12.15 (main, Oct 25 2026, 23:53:29) [GCC 13.2.0]` :

| Groupe | Découverts | Réussis | Ignorés | Échecs / erreurs |
| --- | ---: | ---: | ---: | ---: |
| Lot A — données | 15 | 15 | 0 | 0 |
| Lot A — processus IPC réel | 3 | 3 | 0 | 0 |
| Lot B | 11 | 11 | 0 | 0 |
| Lot C | 9 | 9 | 0 | 0 |
| Lot D | 4 | 3 | 1 | 0 |
| Lot E — scénarios intermodules IPC réel | 3 | 3 | 0 | 0 |
| Tests historiques : mapping, suppression NPS, suppression Google, fusion Google, contrats NPS/questions, réseau, vue Google, réinitialisation | 11 | 10 | 1 | 0 |
| **Total Python** | **56** | **54** | **2** | **0** |

Les 2 ignorés :
1. `test_real_historical_template_when_present` : modèle non accessible dans la copie locale.
2. `test_real_data_when_available` : fichiers métier non distribués dans GitHub.

Contrats Electron :

```text
OPENSSL_CONF=/dev/null node --test electron/preload.test.cjs
```

**6 tests réussis, 0 échec**, avec doubles IPC. Ce n'est pas une recette de la fenêtre Electron. Les tests Python IPC utilisent en revanche un véritable sous-processus `orbite_backend.py`, sans faux routeur.

Compilation syntaxique de la copie Python disponible : réussie. Les anciens tests restent présents, leurs assertions conservées (hors fixtures corrigées au lot A).

Résultats persistés dans `validation/consolidation-results.json`. Les copies utilisées pour les tests ont été vérifiées par empreintes de blobs GitHub ; les tests n'utilisent pas une reconstruction fonctionnelle approximative des modules.

### Matrice de validation fonctionnelle

| Fonction | Contrôle réalisé | Reste à faire |
| --- | --- | --- |
| Démarrage backend | Processus Python réel, réponses JSON | EXE packagé Windows |
| Communication | JSON stdin/stdout réel, contrats preload | Electron complet + EXE |
| Navigation React | Code conservé, intégrations ciblées | TypeScript/build et recette graphique |
| Chargement/filtres | Contrats Python et union géographique | Interactions visuelles |
| Imports NPS | Fichiers synthétiques, doublons, rollback | Fichiers métier réels |
| Imports Google | Référentiel/historique, réimport, confirmations | Jeu métier complet Uberall/historique |
| Suppression/réinitialisation | Tests unitaires et IPC réel, backup, audit | Confirmations dans l'EXE |
| Calculs NPS | Bornes, signes, OPPS pondéré, périodes | Recette métier des identifiants de campagne |
| Calculs Google | Moteur conservé, couverture, filtres, zéro/absence | Cas réels et mois provisoires complets |
| Questions/réseau | Contrats historiques et scénarios IPC | Recette UI |
| Exports Excel | Garde testé avec double du builder | Modèle réel, formules, graphiques, recalcul |
| Sauvegardes | SQLite suppression, rollback, non-mutation Google ; sortie Excel préexistante | Restauration complète de publication Windows |
| Erreurs | IDs, confirmations, fichier modifié, méthodes inconnues | Crash/arrêt Electron, erreurs de packaging |

### Build et CI : non validés

- `npm run build` tenté : **commande indisponible**, aucun compilateur TypeScript exécuté.
- Restauration npm via le registre officiel tentée : **HTTP 403**. Aucun contournement des restrictions réseau.
- Aucun build Electron Windows ni test de sidecar EXE exécuté localement.
- Workflow `.github/workflows/consolidation.yml` étendu aux lots A à E : tests JSON persistés même en cas d'échec ultérieur, modèle contrôlé, tests du sidecar packagé, TypeScript/React, packaging `--publish never`, artefact de recette.
- Aucun résultat de check run retourné par GitHub lors du dernier contrôle. L'existence d'un workflow ne prouve pas son exécution.
- Le workflow `windows.yml` existant reste inchangé. Aucun déploiement ni publication déclenché.

**Lot E non clôturé.** Une réussite de ces 54 tests Python ne valide pas les contrôles manquants.

## Fichiers de cette intervention, par rapport à la fin du lot A

Modifiés — 8 :
- `backend/nps_analytics.py`
- `backend/orbite_data.py`
- `backend/orbite_backend.py`
- `backend/ereputation_bridge.py`
- `src/NpsDashboard.tsx`
- `src/GoogleFusion.tsx`
- `src/main.tsx`
- `.github/workflows/consolidation.yml`

Ajoutés — 10 :
- `backend/periods.py`
- `backend/google_view.py`
- `backend/export_guard.py`
- `backend/run_validation.py`
- `backend/test_consolidation_b.py`
- `backend/test_consolidation_c.py`
- `backend/test_consolidation_d.py`
- `backend/test_consolidation_e.py`
- `validation/consolidation-results.json`
- `CONSOLIDATION_LOTS_B_E.md`

Supprimés : **aucun**. Aucune nouvelle dépendance dans les manifests. Fichiers complets disponibles dans la branche et l'archive GitHub.

## Dépendances entre lots

B et C partagent la normalisation des périodes. D utilise le moteur historique et l'adaptateur de couverture C. E exécute A, B, C, D et les contrats existants. Ces lots ne sont donc pas totalement indépendants ; un retour arrière doit respecter ces dépendances.

## Risques résiduels et clôture

- La validation du modèle Excel et du build Windows est bloquante, pas facultative.
- Les données historiques ambiguës ne sont pas remappées automatiquement.
- Le taux de réponse reste non calculable sans dénominateur métier fiable.
- Les corrections sur les lectures ne prouvent pas que tous les modules existants sont exempts de défauts : notamment restauration `.orbite`, flux Electron et calendrier des données réelles restent à recetter.
- Aucun audit de sécurité exhaustif ni analyse de vulnérabilité des dépendances n'est revendiqué.

Critères restants : build TypeScript/React réussi, EXE Windows compilé et IPC packagé testé, classeur historique exporté/recalculé conforme, recette graphique et métier, validation explicite de livraison. La PR reste en brouillon jusque-là.

## Retour arrière

Avant recette, conserver les exécutables et sauvegarder séparément `orbite.sqlite` et `google.sqlite`. Utiliser uniquement des copies pour les tests destructifs.

Revenir au commit de fin A `2b2eee9dae613bebe42ba73f6e1374587102179d` retire les changements B–E ensemble ; ne pas retirer un seul adaptateur encore importé par le routeur. Cela ne restaure aucune donnée. Toute restauration de bases ou fusion dans main exige une autorisation distincte ; aucune restauration automatique n'est effectuée.
