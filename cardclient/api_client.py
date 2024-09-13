from functools import lru_cache
from logging import getLogger
from typing import Callable, Mapping, Optional
from urllib.parse import urlsplit, urlunsplit

from requests import Session, post
from requests.auth import HTTPBasicAuth
from tenacity import RetryError, Retrying, stop, wait

LOG = getLogger(__name__)


class IdentityAPIClient:
    """
    A client providing methods to query identity related APIs

    """

    @staticmethod
    @lru_cache()
    def _fetch_api_access_token(
        client_id: str,
        client_secret: str,
        token_endpoint: str,
        retry_attempts: int,
        timeout: int,
    ):
        """
        Makes a request to fetch an access token using the client id and secret passed in,
        calling the provided token_endpoint to fetch the access token.

        LRU-cached in order to prevent the unnecessary creation of multiple tokens.

        """
        LOG.info("Fetching access token")
        access_token: Optional[str] = None

        client_auth = HTTPBasicAuth(client_id, client_secret)
        try:
            for attempt in Retrying(
                stop=stop.stop_after_attempt(retry_attempts),
                wait=wait.wait_random(1, 3),
                reraise=True,
            ):
                with attempt:
                    auth_response = post(
                        token_endpoint,
                        data={"grant_type": "client_credentials"},
                        auth=client_auth,
                        timeout=timeout,
                    )

                    auth_data = auth_response.json()
                    status_code = auth_response.status_code
                    if not auth_data.get("access_token"):
                        if auth_data.get("error") and auth_data.get("error").get("description"):
                            LOG.warning(auth_data["error"]["description"])
                        if status_code < 500:
                            LOG.error(f"Auth request indicates client error: {status_code}")
                            break  # break to stop retrying - client credentials are probably bad
                        else:
                            raise RuntimeError(f"Auth request failed with {status_code}")

                    access_token = auth_data["access_token"]
        except RetryError:
            pass

        if not access_token:
            raise RuntimeError("Unable to authenticate using client credentials")

        return access_token

    def __init__(self, config: Optional[Mapping] = {}):
        self.page_size = int(config.get("page_size", 500))
        self.retry_attempts = config.get("retry_attempts", 10)
        self.timeout = config.get("timeout", 10)
        self.r: Session = self._get_authenticated_session(config)

    def _get_authenticated_session(self, config: Mapping):
        """
        Returns a requests.Session authenticated either via Apigee OAuth2 or bearer token
        provided in the url. This method will fail if the Apigee credentials are invalid
        but does not check the access_token provided by Apigee or the bearer token
        passed in the configuration will give access to the API, so calls to the
        API may fail with authorization errors.

        """

        session = Session()
        client_key = config.get("client_key")
        client_secret = config.get("client_secret")

        if client_key and client_secret:
            token = self._get_access_token_from_apigee(
                client_key, client_secret, config.get("token_endpoint")
            )
            session.headers.update({"Authorization": f"Bearer {token}"})

            return session

        if config.get("bearer_token"):
            LOG.info("Using bearer token for authorization")
            session.headers.update({"Authorization": f'Bearer {config["bearer_token"]}'})
        else:
            LOG.warning("No authentication details provided")

        return session

    def _get_access_token_from_apigee(
        self, client_id: str, client_secret: str, token_endpoint: Optional[str] = None
    ):
        """
        Makes a request to Apigee to get an access token, using the client id and secret
        passed in.
        By default the endpoint to use to get the access token is inferred from the base
        url, but this can be overridden using `token_endpoint`.

        """
        if not token_endpoint:
            base_url = urlsplit(self.base_url)
            token_endpoint = urlunsplit((base_url[0], base_url[1], "/oauth2/v1/token", "", ""))

        return IdentityAPIClient._fetch_api_access_token(
            client_id, client_secret, token_endpoint, self.retry_attempts, self.timeout
        )

    def _yield_paged_request(self, url: str, request_method: Optional[Callable] = None, **kwargs):
        """
        Utility method allowing DRF pages to be walked through with results being emitted
        through the returned iterator.

        """

        def make_request(target_url: str, **request_kwargs):
            request = self._request_with_retry(
                target_url, request_method=request_method, **request_kwargs
            )
            data = request.json()
            return data.get("results", []), data.get("next")

        results, next_url = make_request(url, **kwargs)
        yield from results

        while next_url:
            results, next_url = make_request(next_url)
            yield from results

    def _request_with_retry(self, *args, **kwargs):
        """
        Utility method which retries a request using the retry config setup on the class, the
        request method can be used by passing the `request_method` kwarg.

        """

        method = kwargs.pop("request_method", None) or self.r.get
        kwargs.setdefault("timeout", self.timeout)
        try:
            for attempt in Retrying(
                stop=stop.stop_after_attempt(self.retry_attempts),
                wait=wait.wait_random(1, 3),
                reraise=True,
            ):
                with attempt:
                    request = method(*args, **kwargs)
                    request.raise_for_status()

                    return request
        except RetryError:
            pass
