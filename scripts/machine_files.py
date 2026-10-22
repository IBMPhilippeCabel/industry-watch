"""Machine-readable files of a site: robots.txt, sitemap.xml, feed.xml, data.json, llms.txt."""
import json

from common import art_day, esc, updated_iso


def write_machine_files(site, articles, recent, briefing, now, *, site_url, site_name, site_desc,
                        rolling_days, categories, sources):
    """Write robots.txt, sitemap.xml, feed.xml, data.json and llms.txt into `site`."""
    # robots.txt
    (site / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        + "".join(f"User-agent: {bot}\nAllow: /\n\n" for bot in (
            "GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot",
            "ClaudeBot", "Google-Extended", "CCBot"))
        + f"Sitemap: {site_url}sitemap.xml\n",
        encoding="utf-8",
    )

    # sitemap.xml
    months = sorted({(a.get("date") or a["first_seen"].isoformat())[:7] for a in articles}, reverse=True)
    today = f"{now:%Y-%m-%d}"
    urls = [("", today), ("archive/index.html", today)] + [
        (f"archive/{ym}.html", today if ym == months[0] else f"{ym}-28") for ym in months
    ]
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{esc(site_url + p)}</loc><lastmod>{lm}</lastmod></url>\n" for p, lm in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )

    # feed.xml (Atom, 50 latest)
    entries = "".join(
        f'  <entry>\n    <title>{esc(a["title"])}</title>\n'
        f'    <id>{esc(a["link"])}</id>\n'
        f'    <link href="{esc(a["link"])}"/>\n'
        f'    <updated>{art_day(a)}T00:00:00Z</updated>\n'
        f'    <category term="{esc(a["category"])}"/>\n'
        f'    <author><name>{esc(a["source"])}</name></author>\n'
        f'    <summary>{esc(a.get("ai_summary") or a.get("summary", ""))}</summary>\n  </entry>\n'
        for a in recent[:50]
    )
    (site / "feed.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f'  <title>{site_name}</title>\n  <subtitle>{esc(site_desc)}</subtitle>\n'
        f'  <link href="{site_url}feed.xml" rel="self"/>\n  <link href="{site_url}"/>\n'
        f'  <id>{site_url}</id>\n  <updated>{updated_iso(f"{now:%Y-%m-%d %H:%M UTC}")}</updated>\n'
        + entries + "</feed>\n",
        encoding="utf-8",
    )

    # data.json (machine-readable copy of the home page)
    (site / "data.json").write_text(
        json.dumps({
            "site": site_url,
            "updated": updated_iso(f"{now:%Y-%m-%d %H:%M UTC}"),
            "briefing": ({"date": briefing[0], **briefing[1]} if briefing else None),
            "articles": [
                {"title": a["title"], "url": a["link"], "source": a["source"],
                 "category": a["category"], "date": art_day(a),
                 "ai_summary": a.get("ai_summary", ""), "excerpt": a.get("summary", "")}
                for a in recent
            ],
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    # llms.txt
    (site / "llms.txt").write_text(
        f"# {site_name}\n\n"
        f"> {site_desc}\n\n"
        "Content is in English. Articles are collected every two hours from public RSS feeds "
        "(trade publications and news searches) about the subject above; summaries and the daily "
        "briefing are AI-generated, and each item links to its original source.\n\n"
        "## Main pages\n\n"
        f"- [Home]({site_url}): articles of the last {rolling_days} days with the daily briefing\n"
        f"- [Archive]({site_url}archive/index.html): one page per month, all articles\n\n"
        "## Machine-readable\n\n"
        f"- [Atom feed]({site_url}feed.xml): 50 latest articles\n"
        f"- [JSON data]({site_url}data.json): briefing and articles from the last {rolling_days} days\n"
        f"- [Sitemap]({site_url}sitemap.xml)\n\n"
        "## Categories\n\n"
        + "".join(f"- {c}\n" for c in categories)
        + "\n## Sources\n\n"
        + "".join(f"- [{s['name']}]({s['url']}): {s['description']}\n" for s in sources),
        encoding="utf-8",
    )
