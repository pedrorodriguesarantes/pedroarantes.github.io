#!/usr/bin/env python3
"""
build_pubs.py — regenerate publications.html from DBLP, with arXiv preprint links.

Usage:
    python scripts/build_pubs.py            # fast: match preprints via DBLP's own CoRR entries
    python scripts/build_pubs.py --deep     # also query the arXiv API for unmatched papers (slow, ~3s/paper)

Outputs:
    publications.html      — the site page; papers with a known preprint get a [preprint PDF] link
    missing_preprints.md   — checklist of papers with NO arXiv preprint found, so you can upload them

How preprint matching works: DBLP lists your arXiv submissions as separate
"informal" CoRR entries. We normalize titles and match them against the formal
journal/conference versions. --deep additionally searches the arXiv API by
title for anything still unmatched (rate-limited per arXiv's ToS).

No dependencies beyond the Python standard library.
"""

import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

DBLP_PID = "70/3474"
DBLP_URL = f"https://dblp.org/pid/{DBLP_PID}.xml"
ROOT = Path(__file__).resolve().parent.parent
OUT_HTML = ROOT / "publications.html"
OUT_MD = ROOT / "missing_preprints.md"

AWARDS = {
    "conf/icse/TrinkenreichSSG23": "ACM SIGSOFT Distinguished Paper",
    "conf/icse/DiasMCSWP21": "ACM SIGSOFT Distinguished Paper",
    "conf/esem/FelizardoLDCS24": "Best Paper Award",
    "conf/icsm/WesselSWSG20": "IEEE TCSE Distinguished Paper",
    "conf/icse/TrinkenreichBGS22": "Best Paper Award (SEIS)",
}

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Publications — Igor Steinmacher</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="site">
  <div class="row">
    <a class="brand" href="index.html">Igor Steinmacher</a>
    <nav>
      <a href="index.html#research">Research</a>
      <a href="index.html#projects">Projects</a>
      <a href="publications.html">Publications</a>
      <a href="software.html">Software</a>
      <a href="index.html#students">Students</a>
      <a href="index.html#service">Service</a>
      <a href="index.html#contact">Contact</a>
    </nav>
  </div>
</header>
<main>
<section>
<h2>Publications</h2>
<p class="lead">Peer-reviewed journal and conference papers, generated automatically
from <a href="https://dblp.org/pid/70/3474.html" target="_blank" rel="noopener">DBLP</a>.
Papers with an open preprint carry a [preprint PDF] link.</p>
"""

FOOT = """</section>
</main>
<footer>
  <div class="row">
    <span>© Igor Steinmacher · list auto-generated from DBLP</span>
    <a href="https://github.com/igorsteinmacher/igorsteinmacher.github.io" target="_blank" rel="noopener">source</a>
  </div>
</footer>
</body>
</html>
"""

ARXIV_ID_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/|arXiv\.)(\d{4}\.\d{4,5})", re.I)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pubs-builder/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def norm_title(t: str) -> str:
    """Normalize a title for fuzzy matching: lowercase, alphanumerics only."""
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def arxiv_pdf_url(any_url_or_id: str) -> str | None:
    m = ARXIV_ID_RE.search(any_url_or_id or "")
    return f"https://arxiv.org/pdf/{m.group(1)}" if m else None


def arxiv_api_lookup(title: str) -> str | None:
    """Search the arXiv API by exact title. Returns PDF URL or None."""
    q = urllib.parse.quote(f'ti:"{title}"')
    url = f"https://export.arxiv.org/api/query?search_query={q}&max_results=3"
    try:
        root = ET.fromstring(fetch(url))
    except Exception:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    want = norm_title(title)
    for entry in root.findall("a:entry", ns):
        found = entry.findtext("a:title", default="", namespaces=ns)
        if norm_title(found) == want:
            eid = entry.findtext("a:id", default="", namespaces=ns)
            pdf = arxiv_pdf_url(eid)
            if pdf:
                return pdf
    return None


def main() -> None:
    deep = "--deep" in sys.argv
    root = ET.fromstring(fetch(DBLP_URL))

    # Pass 1: harvest arXiv preprints from DBLP's informal CoRR entries
    preprints: dict[str, str] = {}  # normalized title -> arXiv PDF URL
    for r in root.iter("r"):
        pub = r[0]
        if pub.get("publtype") != "informal":
            continue
        title = (pub.findtext("title") or "").strip().rstrip(".")
        for ee in pub.findall("ee"):
            pdf = arxiv_pdf_url(ee.text or "")
            if pdf:
                preprints[norm_title(title)] = pdf
                break

    # Pass 2: formal papers
    by_year: dict[str, list[str]] = defaultdict(list)
    missing: dict[str, list[tuple[str, str, str]]] = defaultdict(list)  # year -> (title, venue, authors)
    n_linked = 0

    for r in root.iter("r"):
        pub = r[0]
        kind = pub.tag
        if kind not in ("article", "inproceedings"):
            continue
        if pub.get("publtype") == "informal":
            continue

        key = pub.get("key", "")
        year = (pub.findtext("year") or "????").strip()
        title = (pub.findtext("title") or "").strip().rstrip(".")
        authors = ", ".join(a.text or "" for a in pub.findall("author"))
        venue = (pub.findtext("journal") or pub.findtext("booktitle") or "").strip()
        ee = pub.findtext("ee") or ""
        vol = pub.findtext("volume")
        pages = pub.findtext("pages")
        detail = ""
        if kind == "article" and vol:
            detail = f" {vol}" + (f": {pages}" if pages else "")

        # preprint lookup: DBLP CoRR first, then (optionally) arXiv API
        pdf = preprints.get(norm_title(title))
        if pdf is None and deep:
            time.sleep(3)  # arXiv API rate-limit etiquette
            pdf = arxiv_api_lookup(title)

        if pdf:
            n_linked += 1
            pre_html = (f'<a class="preprint" href="{esc(pdf)}" target="_blank" '
                        f'rel="noopener">[preprint PDF]</a> ')
        else:
            pre_html = ""
            missing[year].append((title, venue, authors))

        label = "journal" if kind == "article" else "conference"
        award = AWARDS.get(key)
        title_html = (f'<a href="{esc(ee)}" target="_blank" rel="noopener">{esc(title)}</a>'
                      if ee else esc(title))
        award_html = f'<span class="award">★ {esc(award)}</span>' if award else ""

        by_year[year].append(
            f'<div class="pub">\n'
            f'  <div class="meta"><span>{label}</span>'
            f'<span class="venue">{esc(venue)}{esc(detail)}</span>{award_html}</div>\n'
            f'  <div class="title">{pre_html}{title_html}</div>\n'
            f'  <div class="authors">{esc(authors)}</div>\n'
            f"</div>"
        )

    # Write HTML
    parts = [HEAD]
    for year in sorted(by_year, reverse=True):
        parts.append(f'<h3 class="year-h">{year}</h3>')
        parts.extend(by_year[year])
    parts.append(FOOT)
    OUT_HTML.write_text("\n".join(parts), encoding="utf-8")

    # Write missing-preprints checklist
    n_missing = sum(len(v) for v in missing.values())
    md = ["# Papers without an arXiv preprint",
          "",
          f"Generated by `scripts/build_pubs.py`. {n_missing} of "
          f"{n_missing + n_linked} papers have no preprint link.",
          "",
          "Tick a paper after uploading it to arXiv (check the publisher's "
          "self-archiving policy first — most ACM/IEEE venues allow the "
          "author-accepted manuscript).",
          ""]
    for year in sorted(missing, reverse=True):
        md.append(f"## {year}")
        md.append("")
        for title, venue, authors in missing[year]:
            md.append(f"- [ ] **{title}** — *{venue}* — {authors}")
        md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    total = sum(len(v) for v in by_year.values())
    print(f"Wrote {OUT_HTML}: {total} papers, {n_linked} with preprint links.")
    print(f"Wrote {OUT_MD}: {n_missing} papers still need preprints.")
    if not deep and n_missing:
        print("Tip: run with --deep to also search the arXiv API directly.")


if __name__ == "__main__":
    main()
