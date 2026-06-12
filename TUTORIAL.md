# Rebuilding igor.pro.br — Migration Tutorial

**From:** Joomla + T3 (currently showing signs of compromise — see Step 0)
**To:** Static site on GitHub Pages with your custom domain

Total time: ~1–2 hours, most of it waiting for DNS.

---

## Step 0 — Why you're doing this (and why now)

Your current homepage is serving injected spam text ("php shell shell indir
medyum" appears in the rendered page). This is the signature of a compromised
Joomla installation — attackers typically drop a PHP web shell and inject SEO
spam. Even a perfect Joomla rebuild keeps you on the same treadmill: PHP,
database, extensions, and security patches forever.

A static site removes the entire attack surface. There is no server-side code
to exploit, hosting is free, and you maintain it the way you maintain
everything else: with Git.

---

## Step 1 — Set up the repository

You already have `igorsteinmacher/igorsteinmacher.github.io`. Reuse it:

```bash
git clone https://github.com/igorsteinmacher/igorsteinmacher.github.io
cd igorsteinmacher.github.io
# back up whatever is there now
git checkout -b old-site-backup && git push -u origin old-site-backup
git checkout main
```

Copy in the files from this package:

```
index.html
publications.html
style.css
scripts/build_pubs.py
.github/workflows/update-pubs.yml
```

```bash
git add -A
git commit -m "New static site"
git push
```

## Step 2 — Enable GitHub Pages

1. Repository → **Settings → Pages**
2. Source: **Deploy from a branch**, branch `main`, folder `/ (root)`
3. Within a minute the site is live at `https://igorsteinmacher.github.io`

Check it looks right before touching DNS.

## Step 3 — Generate the full publication list

The included `publications.html` is seeded with 2025–2026 papers. Generate the
complete archive (150+ papers, grouped by year, journals and conferences,
arXiv preprints excluded) from DBLP:

```bash
python scripts/build_pubs.py
git add publications.html && git commit -m "Full publication list" && git push
```

The GitHub Action in `.github/workflows/update-pubs.yml` re-runs this on the
1st of every month and commits any changes — your publication page now
updates itself when DBLP indexes a new paper. You can also trigger it manually
from the **Actions** tab.

To mark award papers with a ★, add their DBLP keys to the `AWARDS` dict at the
top of the script.

## Step 4 — Point igor.pro.br at GitHub Pages

At your DNS provider (registro.br or wherever igor.pro.br is managed):

| Type  | Host | Value                |
|-------|------|----------------------|
| A     | @    | 185.199.108.153      |
| A     | @    | 185.199.109.153      |
| A     | @    | 185.199.110.153      |
| A     | @    | 185.199.111.153      |
| CNAME | www  | igorsteinmacher.github.io |

Then in the repo: **Settings → Pages → Custom domain** → enter `igor.pro.br`,
save, and tick **Enforce HTTPS** once the certificate is issued (can take up
to 24 h after DNS propagates). GitHub creates a `CNAME` file in the repo —
keep it.

## Step 5 — Salvage and decommission the old site

Before killing the old hosting:

1. **Export anything you still need** — in Joomla admin, save any article text
   and download `/images/` via FTP/cPanel. Treat every file as untrusted:
   copy only content you recognize, never PHP files.
2. **Don't migrate the Joomla files anywhere.** The compromise likely lives in
   them.
3. Once DNS has switched and the new site is live on igor.pro.br, **cancel or
   wipe the old hosting account**. If the host offers it, ask them to scan/
   purge the account — the web shell may be used to attack other sites on
   shared hosting.
4. Change the passwords you used for that hosting/cPanel/FTP anywhere they
   were reused.

## Step 6 — Day-to-day maintenance

- Edit text → edit the HTML → `git push`. Live in ~30 seconds.
- New paper → do nothing; the monthly Action picks it up from DBLP.
- New section/page → copy the structure of an existing one; `style.css` already
  covers headings, lists, cards, and publication entries.
- Want a news/blog section later → the natural upgrade path is dropping these
  same files into [Astro](https://astro.build) or [Hugo](https://gohugo.io);
  the design carries over since it's plain CSS.

## Customization notes

- **Photo:** add `me.jpg` to the repo and place
  `<img src="me.jpg" alt="Igor Steinmacher" style="max-width:180px;border-radius:8px">`
  in the About section.
- **Colors/type:** everything is tokenized at the top of `style.css`
  (`:root` variables). The palette intentionally echoes the GitHub
  contribution graph — the data your research mines.
- **The contribution-graph strip** in the hero is deterministic (seeded), so
  it renders identically on every visit. Seed and density are in the script
  at the bottom of `index.html`.
- **CV link:** upload `Steinmacher_CV.pdf` to the repo and link it from the
  hero button row.
