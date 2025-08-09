#!/usr/bin/env python3
import os
import shutil
import datetime
import yaml
import frontmatter
from pathlib import Path
from urllib.parse import urlencode
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown as md
import json

ROOT = Path(__file__).parent.resolve()
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
DIST_DIR = ROOT / "dist"

MD = md.Markdown(extensions=[
    "extra",
    "toc",
    "sane_lists",
    "smarty",
])

def load_config():
    with open(ROOT / "config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_env():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["datefmt"] = lambda d, fmt="%d %B %Y": d.strftime(fmt)
    env.filters["tojson"] = lambda obj: json.dumps(obj, ensure_ascii=False)
    env.globals["now"] = datetime.datetime.now
    return env


def reset_dist():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)


def copy_static():
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, DIST_DIR / "static")


def build_redirect_page(env, site, slug, title, target_url):
    # Append default UTM params for attribution
    params = {
        "utm_source": "seo",
        "utm_medium": "affiliate",
        "utm_campaign": slug,
    }
    sep = "&" if ("?" in target_url) else "?"
    final_url = f"{target_url}{sep}{urlencode(params)}"

    out_dir = DIST_DIR / "go" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    html = env.get_template("redirect.html").render(
        site=site,
        title=title,
        target_url=final_url,
        canonical=final_url,
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def load_markdown_posts():
    posts = []
    posts_dir = CONTENT_DIR / "posts"
    if not posts_dir.exists():
        return posts
    for path in sorted(posts_dir.rglob("*.md")):
        fm = frontmatter.load(path)
        html = MD.reset().convert(fm.content)
        meta = fm.metadata
        meta.setdefault("title", path.stem.replace("-", " ").title())
        meta.setdefault("date", datetime.date.today().isoformat())
        meta.setdefault("category", "general")
        meta.setdefault("slug", path.stem)
        meta.setdefault("description", meta.get("excerpt", ""))
        meta.setdefault("affiliate_ctas", [])
        post = {
            "path": path,
            "slug": meta["slug"],
            "title": meta["title"],
            "date": datetime.date.fromisoformat(str(meta["date"]))
                if not isinstance(meta["date"], datetime.date) else meta["date"],
            "category": meta["category"],
            "description": meta.get("description", ""),
            "reading_minutes": max(2, len(fm.content.split()) // 200),
            "html": html,
            "affiliate_ctas": meta.get("affiliate_ctas", []),
        }
        posts.append(post)
    # Newest first
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def render_posts(env, site, posts):
    for post in posts:
        out_dir = DIST_DIR / post["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        html = env.get_template("post.html").render(site=site, post=post)
        (out_dir / "index.html").write_text(html, encoding="utf-8")


def render_index(env, site, posts):
    html = env.get_template("index.html").render(site=site, posts=posts[:12])
    (DIST_DIR / "index.html").write_text(html, encoding="utf-8")


def render_categories(env, site, posts):
    by_cat = {}
    for p in posts:
        by_cat.setdefault(p["category"], []).append(p)
    for cat, cat_posts in by_cat.items():
        out_dir = DIST_DIR / "c" / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        html = env.get_template("category.html").render(site=site, category=cat, posts=cat_posts)
        (out_dir / "index.html").write_text(html, encoding="utf-8")


def render_pages(env, site):
    pages_dir = CONTENT_DIR / "pages"
    if not pages_dir.exists():
        return
    for path in pages_dir.rglob("*.md"):
        fm = frontmatter.load(path)
        html_body = MD.reset().convert(fm.content)
        meta = fm.metadata
        slug = meta.get("slug", path.stem)
        title = meta.get("title", slug.replace("-", " ").title())
        out_dir = DIST_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        html = env.get_template("post.html").render(
            site=site,
            post={
                "slug": slug,
                "title": title,
                "date": datetime.date.today(),
                "category": meta.get("category", "page"),
                "description": meta.get("description", ""),
                "reading_minutes": max(2, len(fm.content.split()) // 200),
                "html": html_body,
                "affiliate_ctas": meta.get("affiliate_ctas", []),
            }
        )
        (out_dir / "index.html").write_text(html, encoding="utf-8")


def render_sitemap(site, posts):
    urls = [site["base_url"].rstrip("/") + "/"]
    urls += [f"{site['base_url'].rstrip('/')}/{p['slug']}/" for p in posts]
    # categories
    cats = sorted(set(p["category"] for p in posts))
    urls += [f"{site['base_url'].rstrip('/')}/c/{c}/" for c in cats]

    # redirects (noindex, but fine to list if you want; here we skip)

    items = []
    today = datetime.date.today().isoformat()
    for u in urls:
        items.append(f"""
  <url>
    <loc>{u}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(items)}
</urlset>
"""
    (DIST_DIR / "sitemap.xml").write_text(xml.strip() + "\n", encoding="utf-8")


def render_robots(site):
    robots = f"""User-agent: *
Allow: /

Sitemap: {site['base_url'].rstrip('/')}/sitemap.xml
"""
    (DIST_DIR / "robots.txt").write_text(robots, encoding="utf-8")


def main():
    site = load_config()
    env = get_env()

    reset_dist()
    copy_static()

    # Redirect pages
    redirects = site.get("redirects", [])
    affiliates = site.get("affiliates", {})
    for r in redirects:
        slug = r["slug"]
        title = r.get("title", slug)
        target = affiliates.get(slug)
        if not target:
            continue
        build_redirect_page(env, site, slug, title, target)

    posts = load_markdown_posts()
    render_posts(env, site, posts)
    render_pages(env, site)
    render_categories(env, site, posts)
    render_index(env, site, posts)

    render_sitemap(site, posts)
    render_robots(site)

    print(f"Built site to {DIST_DIR}")

if __name__ == "__main__":
    main()