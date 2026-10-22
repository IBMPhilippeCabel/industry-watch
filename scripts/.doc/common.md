# `common.py` — fonctions partagées

## But
Regrouper la logique que `build.py`, `render.py` et ses modules doivent appliquer **de la même façon**, pour éviter qu'un
article soit accepté par l'un et rejeté par l'autre. Ce n'est pas un script exécutable : il est importé
(`from common import ...`).

## Fonctions
| Fonction | Entrée | Sortie |
|---|---|---|
| `norm(text)` | une chaîne | minuscules, sans accents, apostrophes `’ ‘ ´` ramenées à `'`, espaces simples. |
| `mentions(norm_text, term)` | texte déjà passé par `norm()`, terme brut | `True` si `term` apparaît comme **mot ou groupe de mots entier**. |
| `site_categories(site_cfg, sources)` | bloc du site + liste de sources | liste des catégories : `categories` de la config, sinon les `default_category` distincts, sinon 4 catégories génériques. |
| `map_category(cat, categories)` | une catégorie stockée + celles du site | la catégorie du site correspondante, ou `None`. |
| `esc`, `art_day`, `updated_iso` | valeur / article / horodatage | échappement HTML, jour d'un article, date ISO 8601 (côté rendu). |
| `icon_src(icon_cfg)` | bloc `site_icon` / `portal_icon` | chemin local (si le fichier existe) sinon URL, sinon `None`. |
| `industries(site_cfg)`, `related_sites(sites, site_cfg)` | bloc du site (+ liste des sites) | ids des marchés d'un compte ; groupes « Industry » / « Accounts » liés. |
| `ROOT`, `ASSETS` | — | racine du dépôt, dossier `scripts/assets/`. |

## Exemples
```python
from common import norm, mentions, map_category

norm("L’Oréal")                                  # "l'oreal"
mentions(norm("New L’Oréal deal"), "L'Oréal")    # True
mentions(norm("extraordinary result"), "extra")  # False  (mot entier)
mentions(norm("Ricardo signs"), "ricard")        # False
map_category("💡 Innovation", ["💡 Innovation & RTD"])   # "💡 Innovation & RTD"
map_category("⚖️ Regulation", ["📈 Market"])             # None
```

## Limites connues
- `mentions()` compare des mots entiers : `loreal` et `l'oreal` restent deux termes distincts (les deux figurent dans `account_filters`).
- `map_category()` repose sur le **libellé** (le texte après l'emoji) : `Innovation` correspond à `Innovation & RTD` mais pas à `Beauty Tech`. Une catégorie sans libellé commun avec celles du site retombe sur `None`.
- Aucun test automatisé ; les exemples ci-dessus ont été vérifiés à la main.
