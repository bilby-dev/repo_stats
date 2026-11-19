import json
from datetime import datetime, timezone


def write_summary(stats, repo_owner, repo_name, cache_dir):
    """
    Write the headline numbers shown on the stats website to a small JSON file.

    Parameters
    ----------
    stats : dict
        Combined citation, commit and issue/PR statistics (as built in `runner.main`)
    repo_owner, repo_name : str
        Repository owner and name on GitHub
    cache_dir : str
        Directory in which to write '{repo_name}_summary.json'

    Returns
    -------
    summary : dict
        The values written to file
    """

    def get(*keys):
        value = stats
        try:
            for key in keys:
                value = value[key]
        except (KeyError, TypeError, IndexError):
            return None
        return value

    def as_int(value):
        return None if value is None else int(value)

    new_authors = get("new_authors") or []
    try:
        # np.unique(..., return_index=True, ...) -> (names, indices, counts)
        n_authors = len(get("unique_authors", 0))
    except TypeError:
        n_authors = None

    summary = {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "age_recent_commit": as_int(get("age_recent_commit")),
        "age_recent_issue_pr": as_int(get("issues", "age_recent")),
        "n_authors": n_authors,
        "n_recent_authors": as_int(get("n_recent_authors")),
        "new_authors": sorted((str(a) for a in new_authors), key=str.lower),
        "issues_recent_open": as_int(get("issues", "recent_open")),
        "issues_recent_close": as_int(get("issues", "recent_close")),
        "prs_recent_open": as_int(get("pullRequests", "recent_open")),
        "prs_recent_close": as_int(get("pullRequests", "recent_close")),
        "cite_all": as_int(get("aggregate", "cite_all")),
        "cite_year": as_int(get("aggregate", "cite_year")),
        "cite_month": as_int(get("aggregate", "cite_month")),
    }

    with open(f"{cache_dir}/{repo_name}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary
