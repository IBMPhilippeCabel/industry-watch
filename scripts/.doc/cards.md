# `cards.py` — cartes d'articles, filtres et briefing

## But
Construire le contenu central d'une page de site : le **bloc briefing**, les **boutons de thèmes**, les **boutons
de marques** et la **grille de cartes**. Module importé par `render.py`, pas un script exécutable.

## Fonctions
| Fonction | Rôle |
|---|---|
| `briefing_block(ctx, briefing)` | bloc « Daily Briefing » : une accroche + une ligne par catégorie **du site** ayant du contenu. Retourne `""` s'il n'y a rien à afficher. |
| `tracked_brands(site_cfg)` | dictionnaire `terme → (slug, nom affiché)` construit depuis `account_filters.owned_brands`, `in_acquisition` et `brands`. |
| `cards_section(ctx, articles)` | boutons de thèmes + boutons de marques + grille de cartes. |
| `art_id(a)` | identifiant stable d'une carte (`a-` + 10 caractères du SHA-1 du lien), utilisé comme ancre. |

`ctx` est le `SiteCtx` défini dans `layout.py` (catégories du site, config du site).

## Règles de filtrage
- **Thèmes** : un bouton par catégorie du site. Une catégorie stockée qui n'existe plus est rangée sous la catégorie **équivalente** (`map_category`) ; sans équivalent, elle garde son nom d'origine.
- **Marques** : détection en **mot entier**, insensible aux accents, à la casse et aux apostrophes (`mentions` de `common.py`), sur **titre + extrait** seulement. Les boutons n'apparaissent que si **au moins 2** marques sont trouvées dans les articles affichés.
- **Doublons de marque** : deux écritures du même nom (accent, apostrophe) donnent le même `slug` ; seule la première est gardée.
- Chaque carte affiche **2 marques au maximum** (ordre alphabétique) mais porte **toutes** les marques détectées dans `data-brands`, donc le filtre fonctionne même pour les marques non affichées.
- Les filtres eux-mêmes sont du JavaScript (`assets/filter.js`), pas du Python.

## Exemple
```python
from cards import tracked_brands

tracked_brands({"brands": ["L'Oréal", "Garnier"]})
# {"l'oréal": ("l-oreal", "L'Oréal"), "garnier": ("garnier", "Garnier")}
```

## Limites connues
- Le nom affiché est la **capitalisation** du terme de la config, avec trois corrections codées en dur (`M&M's`, `RTD`, `ESG`). Un nom de marque particulier (`iPhone`, `eBay`) serait mal écrit.
- Les marques ne sont cherchées que dans le titre et l'extrait : une marque citée seulement dans le corps de l'article n'est pas vue.
- `loreal` et `l'oreal` sont deux termes distincts, donc deux boutons si les deux sont dans `brands` : ils ne sont fusionnés que si leur `slug` est identique.
- Aucun test automatisé.
