# Public portfolio availability

An automated check observes the public portfolio's landing page and six published
language offers. Its observations are available in the
[Public portfolio availability workflow history](https://github.com/MirceaStefanescu/Portfolio/actions/workflows/public-site-availability.yml).

The check is configured hourly at minute 17 UTC, after relevant monitor
configuration or documentation changes on `main`, and for manual runs.
Actual run timestamps in Actions show when an observation occurred; the configured
schedule alone is not evidence of a completed run.

## What is checked

Each page is requested with a bounded HTTP GET. The check verifies its status,
language, canonical URL, title, contact anchor and existing enquiry link.
It does not submit the enquiry form or follow redirects.

## Reading a result

| State | Meaning |
| --- | --- |
| `HEALTHY` | All seven pages returned HTTP 200 and matched the expected page content. |
| `OBSERVED_FAILURE` | This observation found a missing page, a server error or content that failed the page contract. |
| `INCONCLUSIVE` | The check could not establish a result, for example because of a transport error, redirect, rate limit or blocked request. |

The workflow logs and summary retain individual page results. An inconclusive
observation also produces a failed GitHub job, so a red job alone does not
establish that the site is down.

## Limits

This is a point-in-time observation from one client. It does not prove worldwide
reachability, continuous uptime, successful enquiry delivery or the availability
of integrations demonstrated by the portfolio projects.

GitHub hosts both the site and this check. Provider outages or scheduling delays
can affect observations as well as the site. Read the latest completed result and
its timestamp when assessing availability.

The [workflow definition](../.github/workflows/public-site-availability.yml)
provides the public execution configuration.
