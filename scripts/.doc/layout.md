# `layout.py` — gabarit des pages d'un site

## But
Tout ce qui entoure le contenu d'une page de site : `<head>` (SEO, Open Graph, JSON-LD), en-tête avec ses menus
déroulants, pied de page, et la page « Under Construction ». Module importé par `render.py`, pas un script exécutable.

## Le contexte `SiteCtx`
Dataclass qui remplace les anciennes variables globales de `render.py`. Elle est construite **une fois** dans
`render.py` et passée en premier paramètre aux fonctions qui en ont besoin.

| Champ | Contenu |
|---|---|
| `cfg` / `global_cfg` | bloc du site / `config.json` entier. |
| `sources`, `categories` | sources du site ; catégories (boutons de thèmes). |
| `name`, `desc`, `url` | nom, description, URL publique avec `/` final. |
| `rolling_days` | fenêtre de la page d'accueil. |
| `gc_snippet` | balise GoatCounter ou `""`. |
| `css`, `filter_js` | contenu de `assets/site.css` et `assets/filter.js`, inliné dans chaque page. |

## Fonctions
| Fonction | Rôle |
|---|---|
| `shell(ctx, title, body, updated, script, path, description, jsonld, sources_html, archive_html, depth)` | page HTML complète. `depth` = 1 pour `<id>/index.html`, 2 pour les pages d'archive (préfixe `../`). |
| `page_jsonld(ctx, name, path, description, articles)` | données structurées schema.org (`WebSite` + `CollectionPage` + liste de 50 articles max). |
| `jsonld_tag`, `item_list_jsonld` | sérialisation du JSON-LD (échappe `</`) et liste des articles. |
| `site_header_icon`, `favicon_tag` | icône du titre ; favicon (retombe sur l'icône du portail). |
| `footer_html(updated)` | avertissement, mention sur l'icône 🤖 (contenu généré par IA, peut être inexact) + date de mise à jour. |
| `sites_dropdown_html`, `archive_dropdown_html`, `sources_dropdown_html` | trois menus de l'en-tête. |
| `site_relations_html(related)` | lignes « Industry / Accounts » sous le titre d'un site. |
| `render_under_construction(ctx, site, updated)` | page d'attente 🚧 (`assets/under_construction.css`). |

## Exemple
```python
from layout import shell
html = shell(ctx, "L'Oréal Watch — news", "<p>...</p>", "2026-10-22 12:00 UTC", ctx.filter_js, path="loreal/")
```

## Limites connues
- Le HTML est écrit en **chaînes f** : un changement de structure demande de relire `shell()` en entier.
- La liste des sites du menu « Sites » est lue dans `ctx.global_cfg` : une icône absente n'affiche rien (pas de repli emoji).
- `jsonld_tag` écrit `<` et `>` en `\u003c` / `\u003e` : le JSON décodé est identique, mais aucune séquence `<!--` ou `<script` ne peut atteindre le parseur HTML (qui, sinon, pouvait avaler la suite de la page).
- Pas de Content-Security-Policy : elle demanderait de retirer les `onerror` inline et un test en navigateur.
- Le pied de page du portail vit dans `portal.py` (texte presque identique, copié).
- Aucun test automatisé.
