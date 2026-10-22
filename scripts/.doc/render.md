# `render.py` — génération du site statique

## But
Transformer les JSON écrits par `build.py` en **pages HTML statiques** pour un site, plus ses fichiers machine
(sitemap, flux Atom, JSON, `llms.txt`). À chaque exécution il régénère aussi la **page d'accueil du portail**
qui liste tous les sites. Aucun appel réseau, aucune IA.

## Entrées
| Source | Détail |
|---|---|
| `--site <id>` | **obligatoire** : site à rendre (absent → code `2` et usage ; id inconnu → code `1` avec la liste des ids valides). |
| `<output_dir>` | dossier de sortie, argument obligatoire (code `2` sinon). |
| `config.json` | config globale (`site_root_url`, `portal_*`, `goatcounter_url`) et du site (`site_name`, `site_description`, `site_icon`, `rolling_days`, `status`, `categories`, `brands`, `account_filters`). |
| `<sources_file>` | alimente le menu « Sources » et les catégories (quand `categories` est absent). |
| `<data_dir>/**/*.json` et `*.briefing.txt` | articles et dernier briefing. |

## Sorties (dans `<output_dir>`)
| Fichier | Contenu |
|---|---|
| `<id>/index.html` | articles des `rolling_days` derniers jours (30 par défaut), briefing, filtres. |
| `<id>/archive/AAAA-MM.html`, `archive/index.html` | une page par mois (tous les articles) et l'index des mois. |
| `<id>/robots.txt`, `sitemap.xml`, `feed.xml` (Atom, 50 derniers), `data.json`, `llms.txt` | fichiers pour moteurs et agents IA. |
| `<id>/<icône>` | copie de `site_icon.path` pour que l'URL relative marche après déploiement. |
| `index.html` (racine) | portail, régénéré à chaque appel. |
| Code retour | `0` ; `2` si `<output_dir>` manque. |

## Filtres de la page
- **Thèmes** : un bouton par catégorie du site (`categories`, sinon les `default_category` distincts des sources). Un article dont la catégorie stockée n'existe plus (ancien nom) est affiché sous la catégorie **équivalente** du site (`map_category`).
- **Marques** : boutons construits à partir de `account_filters.owned_brands` + `in_acquisition` + `brands`. Affichés si **au moins 2** marques sont trouvées dans les articles affichés. Détection en mot entier, insensible aux accents, à la casse et aux apostrophes.
- **Briefing** : une ligne par catégorie **du site** ayant du contenu.
- **Relations industrie ↔ comptes** : la clé `industry` d'un site compte (id ou liste d'ids) produit une ligne « Industry : … » sous le titre du compte, la ligne inverse « Accounts : … » sur le site marché, et la même mention sur les cartes du portail. Aucune validation : un id inexistant est ignoré, et la relation n'est pas déduite des listes de marques.

## Cas particuliers
- `status: "under_construction"` ou **aucun article** : page d'attente 🚧 à la place du site.
- Un site avec `rolling_days` plus court que l'historique : l'accueil ne montre que la fenêtre, les archives gardent tout.

## Exemples d'exécution
```powershell
# Un site vers un dossier jetable
python scripts/render.py --site loreal .tmp_out
# -> [loreal] index.html: 39 articles (last 30 days); 7 monthly archive page(s); briefing=no

# Tous les sites (ce que fait le workflow, dans le dossier de la branche de publication)
foreach ($s in (python -c "import json;print(' '.join(x['id'] for x in json.load(open('config.json'))['sites']))").Split()) {
  python scripts/render.py --site $s site
}
```
Ouvrir `.tmp_out/index.html` dans un navigateur pour contrôler le rendu (les liens sont relatifs).

## Organisation du code
`render.py` ne fait plus qu'orchestrer (160 lignes : lecture de la config, boucle sur les pages, appels). Le reste est dans des modules du même dossier :

| Fichier | Rôle |
|---|---|
| `scripts/render.py` | point d'entrée : config → `SiteCtx`, `main()` (accueil, archives, copie de l'icône). |
| `scripts/layout.py` | `SiteCtx` (contexte du site), `shell()` (gabarit de page), en-tête, menus déroulants, pied de page, JSON-LD, page « Under Construction ». |
| `scripts/cards.py` | cartes d'articles, filtres thèmes/marques (`tracked_brands`), bloc briefing. |
| `scripts/loader.py` | `load_all(data_dir)` : lecture des JSON, dédoublonnage, dernier briefing. |
| `scripts/machine_files.py` | `robots.txt`, `sitemap.xml`, `feed.xml`, `data.json`, `llms.txt`. |
| `scripts/portal.py` | page d'accueil du portail. |
| `scripts/common.py` | fonctions partagées (voir `common.md`). |
| `scripts/assets/*.css`, `filter.js` | style et script, lus au démarrage et inlinés dans chaque page. |

Les modules ne lisent ni `sys.argv` ni `config.json` : ils reçoivent un `SiteCtx` ou des paramètres, donc leurs fonctions sont importables et testables. Seul `render.py` lit la ligne de commande et la config.

Le HTML produit est **identique octet par octet** à celui d'avant le découpage (6 sites, 107 fichiers, plus les cas « Under Construction » et « aucun article »).

## Limites connues
- Le workflow tente de rendre **tous** les sites même si l'un échoue, publie ceux qui ont réussi, puis fait échouer le job à la fin en nommant les sites en erreur.
- Aucun test automatisé permanent : la non-régression du découpage a été vérifiée par comparaison de rendus, avec un script jetable supprimé ensuite.
- `render.py` lui-même lit `sys.argv` et `config.json` à l'import : seuls ses modules compagnons sont importables seuls.
- Le **portail est réécrit à chaque site rendu** : N rendus = N écritures identiques (inoffensif, mais bruyant).
- Le dernier briefing trouvé sur disque est affiché, même s'il date de plusieurs jours ; sa date est visible dans le bloc.
- Les marques sont comparées à titre + extrait uniquement ; une marque citée seulement dans le corps de l'article n'est pas détectée.
- La liste des mois d'archive inclut aussi les pages déjà présentes dans `<output_dir>`, donc un dossier de sortie qui traîne peut faire apparaître des mois vides (`—`).
- Dépend des modules et de `assets/` du même dossier : lancer le script depuis un autre répertoire reste possible, mais le copier seul ne l'est pas.
