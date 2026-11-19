"""
Build the static stats website from the files written by `repo_stats.runner`.

    python site/build.py --cache cache --out _site

Reads the plots (SVG preferred over PNG, with optional `*_dark` variants) and the
optional `{repo_name}_summary.json` from the cache directory, fills in
`site/template.html` and writes a self-contained site to `--out`.
Standard library only, so it runs without installing anything.
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template

SITE_DIR = Path(__file__).resolve().parent
DEFAULT_PARAMS = SITE_DIR.parent / "repo_stats" / "parameters.json"

# (file key, title, caption) for each plot, in display order
FIGURES = [
    (
        "issues_PRs",
        "Issues and pull requests",
        "Issues and pull requests opened and closed each month, with a rolling average.",
    ),
    (
        "open_items",
        "Open items by label",
        "Currently open issues and pull requests, broken down by label.",
    ),
    (
        "authors",
        "Contributors",
        "Unique commit authors each month, authors with more than one commit, and first-time contributors.",
    ),
    (
        "citations",
        "Citations",
        "Papers citing the bilby papers each year, from NASA ADS.",
    ),
]

IMAGE_EXTS = (".svg", ".png")


def find_image(cache, stem):
    """Return the first existing `cache/stem.{svg,png}`, or None."""
    for ext in IMAGE_EXTS:
        path = cache / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def picture(light, dark, alt, out_img, css_class=""):
    """Copy the image(s) to `out_img` and return a <picture> element."""
    for path in (light, dark):
        if path is not None:
            shutil.copy2(path, out_img / path.name)
    source = ""
    if dark is not None:
        source = (
            f'<source srcset="img/{escape(dark.name)}" '
            'media="(prefers-color-scheme: dark)">'
        )
    cls = f' class="{css_class}"' if css_class else ""
    return (
        f"<picture{cls}>{source}"
        f'<img src="img/{escape(light.name)}" alt="{escape(alt)}" loading="lazy">'
        "</picture>"
    )


def fmt(value):
    return "–" if value is None else f"{value:,}"


def stat_tiles(summary):
    """HTML for the row of headline numbers (empty without a summary file)."""
    if not summary:
        return ""
    days_c = summary.get("age_recent_commit") or 90
    days_i = summary.get("age_recent_issue_pr") or 90
    tiles = [
        (fmt(summary.get("n_recent_authors")), f"active contributors, last {days_c} days",
         f"{fmt(len(summary.get('new_authors') or []))} new"),
        (fmt(summary.get("n_authors")), "contributors all-time", None),
        (fmt(summary.get("prs_recent_close")), f"pull requests closed, last {days_i} days",
         f"{fmt(summary.get('prs_recent_open'))} opened"),
        (fmt(summary.get("issues_recent_close")), f"issues closed, last {days_i} days",
         f"{fmt(summary.get('issues_recent_open'))} opened"),
        (fmt(summary.get("cite_all")), "citing papers all-time",
         f"{fmt(summary.get('cite_year'))} this year"),
    ]
    items = []
    for value, label, sub in tiles:
        sub_html = f'<span class="stat-sub">{escape(sub)}</span>' if sub else ""
        items.append(
            f'<li class="stat"><span class="stat-value">{escape(value)}</span>'
            f'<span class="stat-label">{escape(label)}</span>{sub_html}</li>'
        )
    return '<ul class="stat-grid" aria-label="Headline numbers">' + "".join(items) + "</ul>"


def new_contributors(summary):
    names = (summary or {}).get("new_authors") or []
    if not names:
        return ""
    days = summary.get("age_recent_commit") or 90
    chips = "".join(f"<li>{escape(n)}</li>" for n in names)
    return (
        '<div class="welcome"><h2 class="welcome-title">Welcome, new contributors</h2>'
        f"<p>First commits in the last {days} days. Thank you!</p>"
        f'<ul class="chips">{chips}</ul></div>'
    )


def last_updated(summary, images):
    """Datetime the stats were generated: from the summary, else newest image."""
    if summary and summary.get("generated"):
        try:
            return datetime.fromisoformat(summary["generated"])
        except ValueError:
            pass
    if images:
        mtime = max(p.stat().st_mtime for p in images)
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    return datetime.now(timezone.utc)


def build(cache, out, owner, repo):
    cache, out = Path(cache), Path(out)
    if out.exists():
        shutil.rmtree(out)
    out_img = out / "img"
    out_img.mkdir(parents=True)
    shutil.copytree(SITE_DIR / "static", out / "static")

    summary = None
    summary_file = cache / f"{repo}_summary.json"
    if summary_file.is_file():
        summary = json.loads(summary_file.read_text())
        shutil.copy2(summary_file, out / "summary.json")

    used = []

    cards = []
    for key, title, caption in FIGURES:
        light = find_image(cache, f"{repo}_{key}")
        if light is None:
            print(f"  skipping {key}: no image in {cache}")
            continue
        dark = find_image(cache, f"{repo}_{key}_dark")
        used += [p for p in (light, dark) if p]
        pic = picture(light, dark, f"{title} for {owner}/{repo}", out_img)
        # plots without a dark variant keep their white background in dark mode
        paper = "" if dark else " paper"
        cards.append(
            f'<figure class="plot-card" id="{escape(key)}">'
            f'<a class="plot-media{paper}" href="img/{escape(light.name)}" '
            f'aria-label="Open full-size {escape(title.lower())} plot">{pic}</a>'
            f'<figcaption><h3>{escape(title)}</h3><p>{escape(caption)}</p></figcaption>'
            "</figure>"
        )

    updated = last_updated(summary, used)
    values = {
        "owner": escape(owner),
        "repo": escape(repo),
        "updated_iso": updated.isoformat(timespec="seconds"),
        "updated": updated.strftime("%-d %B %Y"),
        "stat_tiles": stat_tiles(summary),
        "plot_cards": "\n".join(cards),
        "new_contributors": new_contributors(summary),
        "year": str(datetime.now(timezone.utc).year),
    }
    template = Template((SITE_DIR / "template.html").read_text())
    (out / "index.html").write_text(template.substitute(values))
    (out / ".nojekyll").touch()
    print(f"Built {out / 'index.html'} with {len(cards)} plots (updated {values['updated']})")


def main(argv=None):
    params = json.loads(DEFAULT_PARAMS.read_text())
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("-c", "--cache", default="cache", help="runner cache directory")
    parser.add_argument("-o", "--out", default="_site", help="output directory")
    parser.add_argument("--owner", default=params["repo_owner"])
    parser.add_argument("--repo", default=params["repo_name"])
    args = parser.parse_args(argv)
    build(args.cache, args.out, args.owner, args.repo)


if __name__ == "__main__":
    main()
