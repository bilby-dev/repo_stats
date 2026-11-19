from repo_stats.git_metrics import (
    GitMetrics,
    correct_migrated_items,
    deduplicate_commits,
    original_close_date,
)


def _issue(number, created, closed, state="CLOSED"):
    return {
        "node": {
            "number": number,
            "state": state,
            "createdAt": created,
            "updatedAt": created,
            "closedAt": closed,
            "labels": {"edges": []},
        }
    }


def _note(date, text, who="git.ligo:jane.doe"):
    return {"createdAt": date, "body": f"In GitLab by @{who} on Jan 1, 2018, 00:00\n\n{text}"}


def test_original_close_date():
    comments = [
        _note("2018-01-02T00:00:00Z", "Some discussion that mentions closed"),
        _note("2018-01-03T00:00:00Z", "closed"),
        _note("2018-01-04T00:00:00Z", "reopened"),
        _note("2018-02-05T00:00:00Z", "closed via merge request !12"),
        _note("2024-10-03T16:00:00Z", "unassigned @git.ligo:jane.doe"),
        {"createdAt": "2024-10-05T00:00:00Z", "body": "closed"},  # not imported
    ]
    assert original_close_date(comments) == "2018-02-05T00:00:00Z"
    # reopened and never closed again at the source
    assert original_close_date(comments[:3]) is None
    assert original_close_date([]) is None


def test_original_close_date_fallback():
    comments = [
        _note("2020-07-24T00:00:00Z", "Looks good"),
        _note("2021-03-22T00:00:00Z", "This is implemented in !907, so I'm closing the issue."),
        _note("2024-10-03T16:00:00Z", "unassigned @git.ligo:jane.doe"),
        _note("2024-10-05T00:00:00Z", "a comment after the migration"),
    ]
    # no 'closed' note: last real activity, ignoring housekeeping and later comments
    assert original_close_date(comments, before="2024-10-04") == "2021-03-22T00:00:00Z"
    assert original_close_date(comments, before="2024-10-04", fallback_last_activity=False) is None
    # without 'before', the post-migration comment counts as activity
    assert original_close_date(comments) == "2024-10-05T00:00:00Z"
    # an explicit 'closed' note wins over later activity
    comments.insert(1, _note("2020-08-01T00:00:00Z", "closed"))
    assert original_close_date(comments, before="2024-10-04") == "2020-08-01T00:00:00Z"


def test_correct_migrated_items():
    items = [
        # imported, bulk closed, original date known
        _issue(1, "2018-01-01T00:00:00Z", "2024-10-04T08:05:25Z"),
        # imported, bulk closed, original date unknown
        _issue(2, "2018-01-01T00:00:00Z", "2024-10-04T09:00:00Z"),
        # closed for real before the migration
        _issue(3, "2018-01-01T00:00:00Z", "2019-01-01T00:00:00Z"),
        # created on GitHub on the migration day and closed that day
        _issue(4, "2024-10-04T10:00:00Z", "2024-10-04T11:00:00Z"),
        # closed after the bulk closure window
        _issue(5, "2018-01-01T00:00:00Z", "2024-10-06T00:00:00Z"),
        _issue(6, "2018-01-01T00:00:00Z", None, state="OPEN"),
        # created on GitHub shortly before the migration, closed during it
        _issue(7, "2024-09-26T00:00:00Z", "2024-10-04T15:00:00Z"),
    ]
    corrected, n = correct_migrated_items(
        items, "2024-10-04", {1: "2018-04-26T03:27:56Z", 2: None}
    )
    assert n == 2
    assert [i["node"]["closedAt"] for i in corrected] == [
        "2018-04-26T03:27:56Z",
        None,
        "2019-01-01T00:00:00Z",
        "2024-10-04T11:00:00Z",
        "2024-10-06T00:00:00Z",
        None,
        "2024-10-04T15:00:00Z",
    ]
    # input not mutated
    assert items[0]["node"]["closedAt"] == "2024-10-04T08:05:25Z"

    # importer unknown: every item created before and closed during the bulk closure is corrected
    corrected, n = correct_migrated_items(items, "2024-10-04")
    assert n == 3
    assert corrected[6]["node"]["closedAt"] is None
    # wider window catches item 5
    _, n = correct_migrated_items(items, "2024-10-04", window_days=3)
    assert n == 4

    # no-op by default
    unchanged, n = correct_migrated_items(items, None)
    assert unchanged is items and n == 0


def test_process_issues_unknown_close_date():
    items = [
        _issue(1, "2018-01-01T00:00:00Z", None),  # closed, date unknown
        _issue(2, "2018-01-01T00:00:00Z", "2018-03-01T00:00:00Z"),
    ]
    stats = GitMetrics(None, "o", "r", None).process_issues_PRs(
        [items], ["issues"], []
    )["issues"]
    months, counts = stats["close_per_month"]
    assert counts.sum() == 1
    assert dict(zip(months, counts))["2018-03"] == 1
    assert stats["open_per_month"][1].sum() == 2


def _commit(oid, date, name="A", email="a@x.org"):
    return {
        "node": {
            "oid": oid,
            "authoredDate": date,
            "author": {"name": name, "email": email, "user": None},
        }
    }


def test_deduplicate_commits():
    commits = [
        _commit("c", "2020-01-02T00:00:00Z"),
        _commit("b", "2020-01-01T00:00:00Z"),
        _commit("b2", "2020-01-01T00:00:00Z", email="A@X.org"),  # rebased copy
        _commit("d", "2020-01-01T00:00:00Z", name="B", email="b@x.org"),
    ]
    assert [c["node"]["oid"] for c in deduplicate_commits(commits)] == ["c", "b", "d"]


def test_process_commits_dedup():
    commits = [
        _commit("c", "2020-02-02T00:00:00Z"),
        _commit("b", "2020-01-01T00:00:00Z"),
        _commit("b2", "2020-01-01T00:00:00Z"),
        _commit("e", "2020-01-03T00:00:00Z", name="B", email="b@x.org"),
        _commit("f", "2020-01-04T00:00:00Z", name="B", email="b@x.org"),
    ]
    gm = GitMetrics(None, "o", "r", None)
    # 'multi_authors_per_month' is inflated by the duplicate
    with_dup = gm.process_commits(commits)["multi_authors_per_month"]
    dedup = gm.process_commits(commits, dedup=True)["multi_authors_per_month"]
    # January 2020: authors A (duplicated commit) and B (2 commits)
    assert with_dup[1][0] == 2
    assert dedup[1][0] == 1


def test_issue_pr_series_share_months():
    issues = [_issue(1, "2018-03-01T00:00:00Z", "2018-05-01T00:00:00Z")]
    prs = [_issue(2, "2018-11-01T00:00:00Z", None, state="OPEN")]
    stats = GitMetrics(None, "o", "r", None).process_issues_PRs(
        [issues, prs], ["issues", "pullRequests"], []
    )
    series = [
        stats[k][s][0]
        for k in ["issues", "pullRequests"]
        for s in ["open_per_month", "close_per_month"]
    ]
    for months in series:
        assert list(months) == list(series[0])
    assert series[0][0] == "2018-03"
    # PRs: none closed, none opened before 2018-11
    assert stats["pullRequests"]["close_per_month"][1].sum() == 0
    assert stats["pullRequests"]["open_per_month"][1][:8].sum() == 0
