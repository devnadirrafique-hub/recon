"""Small shared HTTP helper for the recon tools.

Standard library only (urllib). Every fetch has a timeout and a size cap,
and every failure becomes a ReconError with a plain-language message. No
credentials are ever sent: these are public, unauthenticated sources.
"""

import urllib.error
import urllib.request

USER_AGENT = "recon-plugin/0.1.0"


class ReconError(Exception):
    """A recon step failed; the message is safe to show to the agent."""


def fetch_text(url, timeout, max_bytes):
    """GET url and return the body as text.

    Raises ReconError on any HTTP error, timeout, oversize response, or
    network failure. Never returns partial or guessed data.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise ReconError("request failed with HTTP %s" % exc.code)
    except TimeoutError:
        raise ReconError("request timed out after %s seconds" % timeout)
    except urllib.error.URLError as exc:
        raise ReconError("could not reach the source (%s)" % exc.reason)
    except Exception as exc:  # keep the tool from crashing the agent loop
        raise ReconError("request failed (%s: %s)" % (type(exc).__name__, exc))
    if len(data) > max_bytes:
        raise ReconError("response too large (over %s bytes)" % max_bytes)
    return data.decode("utf-8", errors="replace")
