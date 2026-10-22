# `portal.py` — page d'accueil du portail

## But
Générer `<output_dir>/index.html` : une carte par site de `config.json`, regroupées par `section`. Module importé par
`render.py`, pas un script exécutable. Aucun accès réseau.

## Fonction
`render_portal(cfg, output_dir, updated, gc_snippet)`

| Paramètre | Détail |
|---|---|
| `cfg` | **toute** la config (`config.json`) : `portal_name`, `portal_description`, `portal_icon`, `site_root_url`, `sites`. |
| `output_dir` | `Path` du dossier de sortie (racine du site publié). |
| `updated` | date de mise à jour déjà formatée (`AAAA-MM-JJ HH:MM UTC`). |
| `gc_snippet` | balise `<script>` GoatCounter, ou `""`. |

## Sorties
- `<output_dir>/index.html`.
- Copie de l'icône du portail (`portal_icon.path`) dans `<output_dir>/` si le fichier existe.

## Contenu de la page
- Cartes groupées par `section` (clé facultative, `Portals` par défaut). Le titre de section n'est affiché que s'il y a **plus d'une** section.
- Chaque carte : icône (fichier local, sinon URL, sinon emoji `default`, sinon 🌐), nom, description, mention 🚧 si `status` vaut `under_construction`.
- Lignes « Industry : … » / « Accounts : … » issues de la clé `industry` des sites (`related_sites` de `common.py`).
- Bouton « 📊 Stats » vers `stats.html`.
- Le style vient de `assets/portal.css`, inliné dans la page.

## Exemple
```python
import json
from pathlib import Path
from portal import render_portal

cfg = json.load(open("config.json", encoding="utf-8"))
render_portal(cfg, Path(".tmp_out"), "2026-10-22 12:00 UTC", "")
# -> Portal index.html written (6 sites)
```

## Limites connues
- **Réécrit à chaque site rendu** par `render.py` : N sites = N écritures identiques (inoffensif, mais bruyant dans les logs).
- `root_url` est calculé mais **jamais utilisé** dans la page : les liens sont relatifs (`<id>/index.html`).
- Le pied de page et le favicon du portail sont propres à ce module ; ceux des sites sont dans `layout.py` (texte presque identique, copié).
- Une icône locale absente retombe sur l'URL puis sur l'emoji, sans aucun message.
- Aucun test automatisé.
