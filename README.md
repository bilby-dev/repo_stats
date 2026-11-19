Repo stats
----------

Functionality to generate git statistics (e.g. commits, issues, pull requests) 
of a repository using GitHub's GraphQL API, and citation statistics using the 
NASA ADS publication database's API.

Produces text files of processed data, and images of summary statistics and 
plots. The images are designed to be used in a README or documentation.

Written for repositories in [The Astropy Project](https://github.com/astropy), 
but readily generalizable by updating the input file `parameters.json` (see 
`parameter_descriptions.json`). Essential parameters to update: 
`repo_owner`, `repo_name`, `labels`, `bibs`. Run with 

```
python -m repo_stats.runner -a "<ADS_TOKEN>" -g "<GITHUB_TOKEN>"
```

where the tokens are for access to the [NASA ADS API](https://ui.adsabs.harvard.edu/help/api/) 
and the [GitHub GraphQL API](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql).

For current output files, see the `cache` branch.



Stats website
-------------

`site/build.py` turns the cache directory into a small static website (plots,
headline numbers from `<repo_name>_summary.json`, light/dark aware) styled to
match [bilby-dev.github.io](https://bilby-dev.github.io). Build and view it
locally with

```
python site/build.py --cache cache --out _site
python -m http.server --directory _site
```

The `update_stats.yml` workflow regenerates the stats daily (or on demand via
*Run workflow*), pushes them to the `cache` branch and deploys the site to
GitHub Pages. To enable it:

1. In the repository's *Settings → Pages*, set *Source* to **GitHub Actions**.
2. In *Settings → Secrets and variables → Actions*, add an `ADS_TOKEN`
   repository secret holding a [NASA ADS API token](https://ui.adsabs.harvard.edu/help/api/).
   (`GITHUB_TOKEN` is provided automatically.)
