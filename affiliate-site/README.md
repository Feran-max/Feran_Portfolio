# Affiliate Static Site

- Build: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python build.py`
- Preview: `cd dist && python3 -m http.server 8080`

Structure:
- `content/` markdown with front matter
- `templates/` Jinja2 templates
- `static/` assets copied to `dist/`
- `config.yml` site settings and affiliate links