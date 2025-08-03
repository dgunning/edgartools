"""
Implements a Hishel cache controller.

The cache controller determines which routes (URLs) may be cached, and for how long to cache them.

This cache controller caches, by default:
- /submissions URLs for up to 10 minutes by default, set in `MAX_SUBMISSIONS_AGE_SECONDS`
- .*index/.* URLs for up to 30 minutes by default, set in `MAX_INDEX_AGE_SECONDS`
- /Archives/edgar/data URLs indefinitely (forever)

"""

import logging
import hishel
import httpcore
from typing import Optional, Union

log = logging.getLogger(__name__)


def custom_key_generator(request: httpcore.Request, body: Optional[bytes]) -> str:
    """Generates a stable, readable key for a given request.

    Args:
        request (httpcore.Request): _description_
        body (bytes): _description_

    Returns:
        str: Persistent key for the request
    """

    host = request.url.host.decode()
    url = request.url.target.decode()

    url_p = url.replace("/", "__")

    key = f"{host}_{url_p}"
    return key


MAX_SUBMISSIONS_AGE_SECONDS = 10 * 60  # Check for submissions every 10 minutes
MAX_INDEX_AGE_SECONDS = 30 * 60  # Check for updates to index (ie: daily-index) every 30 minutes


def get_cache_controller(**kwargs):
    class EdgarController(hishel.Controller):
        def is_cachable(self, request: httpcore.Request, response: httpcore.Response) -> bool:
            if request.url.host.decode().endswith("sec.gov"):
                target = request.url.target.decode()
                if target.startswith("/submissions") or target.startswith("/include/ticker.txt") or target.startswith("/files/company_tickers.json"):
                    # /submissions are marked "no-store", but we're going to override this and allow it to be cached for MAX_SUBMISSIONS_AGE_SECONDS
                    return True
                elif "index/" in target:
                    # /Archives are immutable are marked "no-cache"
                    return True
                elif target.startswith("/Archives/edgar/data"):
                    # /Archives data are immutable are marked "no-cache"
                    return True

            super_is_cachable = super().is_cachable(request, response)
            log.debug("%s is cacheable %s", request.url, super_is_cachable)
            return super_is_cachable

        def construct_response_from_cache(
            self, request: httpcore.Request, response: httpcore.Response, original_request: httpcore.Request
        ) -> Union[httpcore.Request, httpcore.Response, None]:
            target = request.url.target.decode()

            if request.url.host.decode().endswith("sec.gov"):
                if target.startswith("/submissions") or target.startswith("/include/ticker.txt") or target.startswith("/files/company_tickers.json"):
                    max_age = MAX_SUBMISSIONS_AGE_SECONDS
                elif "index/" in target:
                    max_age = MAX_INDEX_AGE_SECONDS
                elif target.startswith("/Archives/edgar/data"):
                    # Cache forever, never recheck
                    log.debug("Cache hit for %s", target)
                    return response
                else:
                    max_age = None  # Fall through default cache handler

                if max_age:
                    age_seconds = hishel._controller.get_age(response, self._clock)

                    # log.debug("Submissions age is %d, max_age is %d", age_seconds, max_age)
                    if age_seconds > max_age:
                        log.debug("Request needs to be validated before using %s (age=%d, max_age=%d)", target, age_seconds, max_age)
                        return request
                    else:
                        log.debug("Cache hit for %s (age=%d, max_age=%d)", target, age_seconds, max_age)
                        return response

            log.debug("Falling through to default cache policy for %s", target)
            return super().construct_response_from_cache(request, response, original_request)

    controller = EdgarController(cacheable_methods=["GET", "POST"], cacheable_status_codes=[200], key_generator=custom_key_generator, **kwargs)

    return controller
