"""
Plots of repository and citation statistics.

Every plot is drawn twice, once for light and once for dark backgrounds, using
the palette and typography of the bilby website (https://bilby-dev.github.io).
For a figure with stem ``<repo_name>_<plot>`` the following files are written
to ``cache_dir``:

- ``<repo_name>_<plot>.png`` / ``.svg``: light theme (white background)
- ``<repo_name>_<plot>_dark.png`` / ``.svg``: dark theme
"""

import contextlib
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from repo_stats.utilities import rolling_average

FONT_DIR = Path(__file__).resolve().parent.parent / "dashboard_template"
for _font in sorted(FONT_DIR.glob("SourceSans3-*.ttf")):
    font_manager.fontManager.addfont(str(_font))

# Categorical series colors were validated for color-vision deficiency and
# contrast against each theme's background. Slot 1 is the bilby brand blue.
# Slots 4+ only appear if more than three papers are tracked.
THEMES = {
    "light": {
        "suffix": "",
        "bg": "#ffffff",
        "ink": "#0b2540",
        "muted": "#4b6782",
        "grid": "#d6e4f1",
        "axis": "#9cb6cf",
        "series": ["#1d67b0", "#e0702c", "#13976a", "#6250d6", "#c23c7e"],
    },
    "dark": {
        "suffix": "_dark",
        "bg": "#0a1622",
        "ink": "#e6eff8",
        "muted": "#9db3c9",
        "grid": "#1f3850",
        "axis": "#2b4966",
        "series": ["#3f8ad6", "#d9692f", "#1a9f6f", "#9085e9", "#d55181"],
    },
}

# kept for backwards compatibility
cs = THEMES["light"]["series"]
ms = ["o", "s", "D", "^", "v", "P"]

DPI = 200
RAW_ALPHA = 0.35


def _generated_on():
    return datetime.now(timezone.utc).strftime("%B %d, %Y")


@contextlib.contextmanager
def _themed(theme):
    """Context manager applying matplotlib rcParams for the given theme."""
    t = THEMES[theme]
    rc = {
        "font.family": "sans-serif",
        "font.sans-serif": ["Source Sans 3", "DejaVu Sans"],
        "font.size": 12,
        "figure.facecolor": t["bg"],
        "axes.facecolor": t["bg"],
        "savefig.facecolor": t["bg"],
        "text.color": t["ink"],
        "axes.labelcolor": t["muted"],
        "axes.edgecolor": t["axis"],
        "axes.linewidth": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.titlesize": 16,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.titlecolor": t["ink"],
        "axes.labelsize": 12,
        "axes.prop_cycle": plt.cycler(color=t["series"]),
        "grid.color": t["grid"],
        "grid.linewidth": 0.8,
        "xtick.color": t["muted"],
        "ytick.color": t["muted"],
        "xtick.labelcolor": t["muted"],
        "ytick.labelcolor": t["muted"],
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "ytick.major.size": 0,
        "xtick.major.size": 4,
        "lines.linewidth": 2.2,
        "lines.solid_capstyle": "round",
        "lines.markersize": 7,
        "legend.frameon": False,
        "legend.fontsize": 11,
        "legend.labelcolor": t["ink"],
        "svg.fonttype": "path",
    }
    with plt.rc_context(rc):
        yield t


def _titles(ax, title, subtitle, t):
    """Left-aligned title with a muted subtitle underneath."""
    ax.set_title(title, pad=30)
    ax.annotate(
        subtitle,
        xy=(0, 1),
        xycoords="axes fraction",
        xytext=(0, 10),
        textcoords="offset points",
        ha="left",
        va="bottom",
        color=t["muted"],
        fontsize=11.5,
    )


def _save(fig, cache_dir, stem, t):
    for ext in ("png", "svg"):
        fig.savefig(f"{cache_dir}/{stem}{t['suffix']}.{ext}", dpi=DPI)


def _render(draw, cache_dir, stem):
    """Draw and save the figure for each theme; return the light-theme figure."""
    figs = {}
    for theme in THEMES:
        with _themed(theme) as t:
            fig = draw(t)
            _save(fig, cache_dir, stem, t)
        figs[theme] = fig
    for theme, fig in figs.items():
        if theme != "light":
            plt.close(fig)
    return figs["light"]


def _to_dates(months):
    return [datetime.strptime(str(m), "%Y-%m") for m in months]


def _centered(x, window):
    """Trim 'x' to align with the output of a centered rolling average."""
    cut = window // 2
    return x[cut : len(x) - cut]


def _date_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    ax.tick_params(axis="x", which="minor", length=2)
    ax.margins(x=0.01)


def _style_handles(t, window_avg):
    return [
        Line2D([], [], color=t["muted"], lw=1, alpha=0.6, label="Monthly"),
        Line2D([], [], color=t["muted"], lw=2.2, label=f"{window_avg}-month rolling average"),
    ]


def _monthly_series(ax, months, values, color, window_avg, rolling=True):
    """Plot raw monthly values (thin, faded) and their rolling average (bold)."""
    dates = _to_dates(months)
    ax.plot(dates, values, color=color, lw=1, alpha=RAW_ALPHA)
    if rolling and len(values) >= window_avg:
        roll_avg, window_avg = rolling_average(values, window_avg)
        ax.plot(_centered(dates, window_avg), roll_avg, color=color)
    return window_avg


def author_time_plot(commit_stats, repo_owner, repo_name, cache_dir, window_avg=7):
    """
    Plot respository commit authors over time.

    Arguments
    ---------
    commit_stats : dict
        Dictionary including commit statistics. See `git_metrics.Gits.process_commits()`
    repo_owner : str
        Owner of repository (for labels)
    repo_name : str
        Name of repository (for labels and figure savename)
    cache_dir : str
        Name of directory in which to cache figure
    window_avg : int, default=7
        Number of months for rolling average of commit data. Enforced to be odd.

    Returns
    -------
    fig : `plt.figure` instance
        The generated (light theme) figure
    """
    print("\nMaking figure: commit authors over time")

    # don't include current month (if it's early in the month, result biased low)
    series = [
        ("All authors", *[x[:-1] for x in commit_stats["authors_per_month"]]),
        ("Authors with >1 commit", *[x[:-1] for x in commit_stats["multi_authors_per_month"]]),
        ("New authors", *[x[:-1] for x in commit_stats["new_authors_per_month"]]),
    ]
    if window_avg % 2 == 0:
        window_avg -= 1

    def draw(t):
        fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
        handles = []
        for ii, (label, months, values) in enumerate(series):
            color = t["series"][ii]
            _monthly_series(ax, months, values, color, window_avg)
            handles.append(Line2D([], [], color=color, label=label))

        _date_axis(ax)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylabel("Authors per month")
        _titles(
            ax,
            f"Commit authors to {repo_owner}/{repo_name}",
            f"Unique authors per month · generated {_generated_on()}",
            t,
        )
        fig.legend(
            handles=handles + _style_handles(t, window_avg),
            loc="outside lower center",
            ncol=5,
            handlelength=1.8,
            columnspacing=1.6,
        )
        return fig

    return _render(draw, cache_dir, f"{repo_name}_authors")


def citation_plot(cite_stats, repo_name, cache_dir, names=None):
    """
    Plot citations to referenced papers over time.

    Citations dated before a paper's publication year (as given by the first
    four characters of its bibcode) are dropped, since these are errors in the
    ADS database.

    Arguments
    ---------
    cite_stats : dict
        Dictionary including citation statistics. See `citation_metrics.Cites.aggregate_citations()`
    repo_name : str
        Name of repository (for labels and figure savename)
    cache_dir : str
        Name of directory in which to cache figure
    names : list of str, optional
        Name of referenced papers (for plot legend)

    Returns
    -------
    fig : `plt.figure` instance
        The generated (light theme) figure
    """
    print("\nMaking figure: citations over time")

    today = datetime.now(timezone.utc)
    this_year = today.year
    days_in_year = 366 if this_year % 4 == 0 and (this_year % 100 != 0 or this_year % 400 == 0) else 365
    year_frac = today.timetuple().tm_yday / days_in_year

    keys = list(cite_stats)
    if names is None:
        names = keys
    pub_years = [int(k[:4]) for k in keys if k[:4].isdigit()]
    first_year = min(pub_years) if pub_years else None

    curves = []
    for ii, key in enumerate(keys):
        years, counts = (np.asarray(x) for x in cite_stats[key]["cite_per_year"])
        min_year = int(key[:4]) if key[:4].isdigit() else first_year
        if min_year is not None:
            keep = years >= min_year
            years, counts = years[keep], counts[keep]
        full = years < this_year
        ytd = int(counts[years == this_year].sum())
        curves.append(
            {
                "name": names[ii],
                "aggregate": key == "aggregate",
                "years": years[full],
                "counts": counts[full],
                "ytd": ytd,
                "projected": ytd / year_frac,
                "total": int(counts.sum()),
            }
        )

    def draw(t):
        fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
        handles = []
        n_paper = 0
        for ii, c in enumerate(curves):
            if c["aggregate"]:
                color, ls, marker = t["ink"], (0, (4, 2.5)), None
            else:
                color, ls, marker = t["series"][n_paper % len(t["series"])], "-", ms[n_paper % len(ms)]
                n_paper += 1
            ax.plot(
                c["years"],
                c["counts"],
                color=color,
                ls=ls,
                marker=marker,
                mec=t["bg"],
                mew=1.2,
                zorder=3,
            )
            if len(c["years"]):
                # dotted segment from last complete year to this year's projection
                ax.plot(
                    [c["years"][-1], this_year],
                    [c["counts"][-1], c["projected"]],
                    color=color,
                    ls=":",
                    lw=1.6,
                    zorder=2,
                )
            ax.plot(
                this_year,
                c["projected"],
                marker=marker or "o",
                ls="",
                mfc=t["bg"],
                mec=color,
                mew=1.8,
                zorder=4,
            )
            ax.plot(
                this_year - 1 + year_frac,
                c["ytd"],
                marker=marker or "o",
                ls="",
                ms=5.5,
                color=color,
                alpha=0.8,
                zorder=4,
            )
            handles.append(
                Line2D(
                    [],
                    [],
                    color=color,
                    ls=ls,
                    marker=marker,
                    mec=t["bg"],
                    label=f"{c['name']}: {c['total']:,}",
                )
            )

        handles += [
            Line2D([], [], ls="", marker="o", ms=5.5, color=t["muted"], label="Year to date"),
            Line2D(
                [],
                [],
                ls=":",
                lw=1.6,
                marker="o",
                mfc=t["bg"],
                mec=t["muted"],
                mew=1.8,
                color=t["muted"],
                label=f"Projected {this_year} (from year to date)",
            ),
        ]

        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylim(bottom=0)
        ax.set_ylabel("Refereed citations per year")
        _titles(
            ax,
            f"Refereed citations to {repo_name}",
            f"Data from NASA ADS · totals in legend · generated {_generated_on()}",
            t,
        )
        fig.legend(handles=handles, loc="outside lower center", ncol=3, handlelength=2.4)
        return fig

    return _render(draw, cache_dir, f"{repo_name}_citations")


def open_issue_PR_plot(issue_pr_stats, repo_name, cache_dir):
    """
    Plot a bar chart of a repository's currently open issues and pull requests, per label.

    Arguments
    ---------
    issue_pr_stats : list of dict
        Statistics for issues and pull requests (see `git_metrics.Gits.process_issues_PRs`)
    repo_name : str
        Name of repository (for labels and figure savename)
    cache_dir : str
        Name of directory in which to cache figure

    Returns
    -------
    fig : `plt.figure` instance
        The generated (light theme) figure
    """
    print("\nMaking figure: currently open issues and pull requests")

    issues = issue_pr_stats["issues"]["label_open"]
    prs = issue_pr_stats["pullRequests"]["label_open"]
    labels = list(issues)
    # most open items at the top
    labels.sort(key=lambda x: (issues[x] + prs.get(x, 0), x.lower()))
    n_issue = np.array([issues[x] for x in labels])
    n_pr = np.array([prs.get(x, 0) for x in labels])

    def draw(t):
        height = max(4.5, 0.32 * len(labels) + 2.2)
        fig, ax = plt.subplots(figsize=(10, height), layout="constrained")
        y = np.arange(len(labels))
        bar_h = 0.4
        ax.barh(y + bar_h / 2, n_issue, height=bar_h, color=t["series"][0], label="Open issues", edgecolor=t["bg"], linewidth=1)
        ax.barh(y - bar_h / 2, n_pr, height=bar_h, color=t["series"][1], label="Open PRs", edgecolor=t["bg"], linewidth=1)
        ax.set_yticks(y, labels, color=t["ink"])
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", length=0, pad=6)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylim(-0.6, len(labels) - 0.4)
        ax.set_xlabel("Currently open")
        _titles(
            ax,
            f"Open issues and PRs in {repo_name} by label",
            f"Items with several labels are counted once per label · generated {_generated_on()}",
            t,
        )
        fig.legend(loc="outside lower center", ncol=2)
        return fig

    return _render(draw, cache_dir, f"{repo_name}_open_items")


def issue_PR_time_plot(issue_pr_stats, repo_owner, repo_name, cache_dir, window_avg=7):
    """
    Plot a repository's number of issues and pull requests opened and closed over time.

    Arguments
    ---------
    issue_pr_stats : list of dict
        Statistics for issues and pull requests (see `git_metrics.Gits.process_issues_PRs`)
    repo_owner : str
        Owner of repository (for labels)
    repo_name : str
        Name of repository (for labels and figure savename)
    cache_dir : str
        Name of directory in which to cache figure
    window_avg : int, default=7
        Number of months for rolling average of commit data. Enforced to be odd.

    Returns
    -------
    fig : `plt.figure` instance
        The generated (light theme) figure
    """
    print("\nMaking figure: issues and pull requests over time")

    if window_avg % 2 == 0:
        window_avg -= 1

    # don't include current month (if it's early in the month, result biased low)
    panels = []
    for key, title in [("pullRequests", "Pull requests"), ("issues", "Issues")]:
        panels.append(
            (
                title,
                [x[:-1] for x in issue_pr_stats[key]["open_per_month"]],
                [x[:-1] for x in issue_pr_stats[key]["close_per_month"]],
            )
        )

    def draw(t):
        fig, axes = plt.subplots(
            2, 1, figsize=(10, 7.5), sharex=True, layout="constrained"
        )
        for ax, (title, opened, closed) in zip(axes, panels):
            _monthly_series(ax, *opened, t["series"][0], window_avg)
            _monthly_series(ax, *closed, t["series"][1], window_avg)
            ax.text(
                0.005,
                0.97,
                title,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=13,
                fontweight="semibold",
                color=t["ink"],
            )
            ax.set_ylabel("Per month")
            ax.set_ylim(bottom=0)
            ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
            _date_axis(ax)
        axes[0].tick_params(axis="x", which="both", length=0)

        _titles(
            axes[0],
            f"Issues and PRs in {repo_owner}/{repo_name}",
            f"Opened and closed per month · generated {_generated_on()}",
            t,
        )
        handles = [
            Line2D([], [], color=t["series"][0], label="Opened"),
            Line2D([], [], color=t["series"][1], label="Closed"),
        ] + _style_handles(t, window_avg)
        fig.legend(handles=handles, loc="outside lower center", ncol=4, handlelength=1.8)
        return fig

    return _render(draw, cache_dir, f"{repo_name}_issues_PRs")
