from base64 import b64encode
from typing import Mapping, Optional
from unittest import TestCase

import requests_mock
from identitylib.identifiers import IdentifierSchemes
from requests import exceptions
from requests.models import HTTPError

from ..card_client import CardClient, LegacyCardholderClient
from ..identifiers import CRSID_SCHEME, identifier_schemes


class TestCardParsingMethods(TestCase):
    card_with_all_ids = {
        "id": "card-with-identifiers",
        "identifiers": [
            {"scheme": str(IdentifierSchemes.CRSID), "value": "wgd23"},
            {"scheme": str(IdentifierSchemes.USN), "value": "300001"},
            {"scheme": str(IdentifierSchemes.STAFF_NUMBER), "value": "1000"},
            {"scheme": str(IdentifierSchemes.BOARD_OF_GRADUATE_STUDIES), "value": "5"},
            {"scheme": str(IdentifierSchemes.LEGACY_CARDHOLDER), "value": "aa000a1"},
            {"scheme": str(IdentifierSchemes.MIFARE_ID), "value": "11201010"},
            {"scheme": str(IdentifierSchemes.MIFARE_NUMBER), "value": "32424121479"},
            {"scheme": str(IdentifierSchemes.LEGACY_CARD), "value": "1324352"},
            {"scheme": str(IdentifierSchemes.PHOTO), "value": "1"},
            {"scheme": str(IdentifierSchemes.BARCODE), "value": "VE1212"},
        ],
    }

    def test_normalize_card_handles_all_identifiers(self):
        self.assertEqual(
            CardClient.normalize_card(TestCardParsingMethods.card_with_all_ids),
            {
                "barcode": "ve1212",
                "bgs_id": "5",
                "crsid": "wgd23",
                "id": "card-with-identifiers",
                "legacy_card_holder_id": "aa000a1",
                "legacy_card_id": "1324352",
                "mifare_id": "11201010",
                "mifare_id_hex": "00aae9f2",
                "mifare_number": "32424121479",
                "photo_id": "1",
                "staff_number": "1000",
                "usn": "300001",
            },
        )

    def test_normalize_card_handles_missing_identifiers(self):
        test_card = {
            "id": "card-with-one-identifier",
            "identifiers": [
                {"scheme": str(IdentifierSchemes.CRSID), "value": "wgd23"},
            ],
        }

        self.assertEqual(
            CardClient.normalize_card(test_card),
            {
                "barcode": "",
                "bgs_id": "",
                "crsid": "wgd23",
                "id": "card-with-one-identifier",
                "legacy_card_holder_id": "",
                "legacy_card_id": "",
                "mifare_id": "",
                "mifare_id_hex": "",
                "mifare_number": "",
                "photo_id": "",
                "staff_number": "",
                "usn": "",
            },
        )

    def test_normalize_card_will_add_all_fields_from_card_dto(self):
        test_card = {
            "id": "card-with-additional_fields",
            "issuedAt": "2005-05-24T08:57:06Z",
            "issueNumber": 7,
            "random_boolean_field": True,
            "identifiers": [],
        }

        self.assertEqual(
            CardClient.normalize_card(test_card),
            {
                "barcode": "",
                "bgs_id": "",
                "crsid": "",
                "id": "card-with-additional_fields",
                "legacy_card_holder_id": "",
                "legacy_card_id": "",
                "mifare_id": "",
                "mifare_id_hex": "",
                "mifare_number": "",
                "photo_id": "",
                "staff_number": "",
                "usn": "",
                "issuedAt": "2005-05-24T08:57:06Z",
                "issueNumber": 7,
                "random_boolean_field": True,
            },
        )

    def test_get_identifier_by_scheme_can_find_all_ids(self):
        test_card = TestCardParsingMethods.card_with_all_ids

        for id_scheme in identifier_schemes:
            expected_val = next(
                (id["value"] for id in test_card["identifiers"] if id["scheme"] == id_scheme)
            )
            self.assertEqual(
                CardClient.get_identifier_by_scheme(test_card, id_scheme),
                f"{expected_val}@{id_scheme}".lower(),
            )

    def test_get_identifier_by_scheme_returns_none_for_no_matching_identifer(self):
        test_card = {"identifiers": []}

        for id_scheme in identifier_schemes:
            self.assertIsNone(CardClient.get_identifier_by_scheme(test_card, id_scheme))


class CardAPITestMixin:
    """
    Mixin that provides convenience methods for constructing a card client and card client urls

    """

    base_url = "https://card-api.com"

    def make_client(self, config: Optional[Mapping] = {}):
        return CardClient({"base_url": self.base_url, **config})

    def api_url(self, path: str, version: Optional[str] = CardClient.default_version):
        return f"{self.base_url}/{version}{path}"


class TestIdentityAPIClient(TestCase, CardAPITestMixin):
    @requests_mock.Mocker()
    def test_identity_client_will_use_apigee_credentials(self, mocker):
        """
        Test that card client will use Apigee client credentials

        """
        # expect an auth request which returns an access token
        auth_request = mocker.post(
            f"{self.base_url}/oauth2/v1/token", json={"access_token": "mock_access_token"}
        )

        client = self.make_client({"client_key": "c_id_123", "client_secret": "x1"})

        # ensure the auth request was sent with the client credentials in the auth header
        self.assertEqual(
            auth_request.request_history[0].headers["Authorization"],
            f'Basic {b64encode(b"c_id_123:x1").decode("utf-8")}',
        )

        # setup a mock for a single card detail request and query for a card detail
        card_request = mocker.get(self.api_url("/cards/card-id/"), json={"id": "test-card-id"})
        client.get_card_detail("card-id")

        # the card request should contain the access token within the auth header
        self.assertEqual(
            card_request.request_history[0].headers["Authorization"], "Bearer mock_access_token"
        )

    @requests_mock.Mocker()
    def test_identity_client_will_fail_with_bad_apigee_creds(self, mocker):
        """
        Test that card client will fail to init if Apigee credentials are incorrect

        """
        # Throw a 401 in response to the auth request
        mocker.post(
            f"{self.base_url}/oauth2/v1/token",
            exc=exceptions.HTTPError("401 Invalid Client Credentials"),
        )

        with self.assertRaises(exceptions.HTTPError):
            self.make_client({"client_key": "client_id", "client_secret": "a99"})

        # Respond with 200 but no access_token in the body
        mocker.post(
            f"{self.base_url}/oauth2/v1/token",
            json={"error": {"description": "Something went wrong"}},
        )

        with self.assertRaisesRegex(
            RuntimeError, expected_regex="Unable to authenticate using client credentials"
        ):
            self.make_client({"client_key": "client_id", "client_secret": "a99"})

    @requests_mock.Mocker()
    def test_identity_client_will_authenticate_against_apigee_with_custom_url(self, mocker):
        """
        Test that card client will use custom token endpoint provided

        """
        # except a post to our custom endpoint
        token_request = mocker.post(
            "https://authentication.io/gimme-token/", json={"access_token": "custom-access-token"}
        )
        client = self.make_client(
            {
                "token_endpoint": "https://authentication.io/gimme-token/",
                "client_key": "client_id",
                "client_secret": "a99",
            }
        )

        # setup a mock for a single card detail request and query for a card detail
        card_request = mocker.get(self.api_url("/cards/card-id/"), json={"id": "test-card-id"})
        client.get_card_detail("card-id")

        print(token_request.request_history[0].body)

        # the token request should specify the grant_type as the data payload
        self.assertEqual(token_request.request_history[0].body, "grant_type=client_credentials")

        # the card request should contain the access token from our custom endpoint
        self.assertEqual(
            card_request.request_history[0].headers["Authorization"], "Bearer custom-access-token"
        )

    @requests_mock.Mocker()
    def test_identity_client_will_only_use_apigee_creds_if_all_present(self, mocker):
        """
        Test that card client will only use apigee credentials if `client_key` and
        `client_secret` are provided

        """
        # create a client without `client_key` - no request to Apigee is made for an
        # access token
        client = self.make_client(
            {
                "token_endpoint": "https://authentication.io/gimme-token/",
                "apigee_client": "misnamed-client-id",
                "client_secret": "a99",
            }
        )

        # setup a mock for a single card detail request and query for a card detail
        card_request = mocker.get(self.api_url("/cards/card-id/"), json={"id": "test-card-id"})
        client.get_card_detail("card-id")

        # the card request should not contain an Authorization header
        self.assertIsNone(card_request.request_history[0].headers.get("Authorization"))

    @requests_mock.Mocker()
    def test_identity_client_will_use_bearer_token_provided(self, mocker):
        """
        Test that card client will use the bearer token provided in config

        """
        # create a client with a bearer token
        client = self.make_client({"bearer_token": "test-token"})

        # setup a mock for a single card detail request and query for a card detail
        card_request = mocker.get(self.api_url("/cards/card-id/"), json={"id": "test-card-id"})
        client.get_card_detail("card-id")

        # the card request should contain the access token from our custom endpoint
        self.assertEqual(
            card_request.request_history[0].headers["Authorization"], "Bearer test-token"
        )


class TestCardClientInit(TestCase, CardAPITestMixin):
    @requests_mock.Mocker()
    def test_card_client_handles_leading_slash_in_base_url(self, mocker):
        """
        Test that the leading slash in the base url is ignored

        """
        client = self.make_client({"base_url": "https://test.com/", "page_size": 0})
        mocker.get(f"https://test.com/{CardClient.default_version}/cards/?page_size=0", json={})

        response = list(client.all_cards())
        self.assertListEqual(response, [])

    @requests_mock.Mocker()
    def test_card_client_adds_api_version(self, mocker):
        """
        Test that the card client includes the api version in the url

        """
        # setup a client with a specific api version
        client = self.make_client({"api_version": "v1alpha999"})

        # setup a request mock for a card detail request with the api version
        mocker.get(f"{self.base_url}/v1alpha999/cards/any-card/", json={"id": "any-card"})

        response = client.get_card_detail("any-card")
        self.assertEqual(response, {"id": "any-card"})

    @requests_mock.Mocker()
    def test_card_client_uses_default_api_version(self, mocker):
        """
        Test that the card client uses default API version if non is specified

        """
        # setup a client with no api version
        client = self.make_client()

        # setup a request mock for a card detail request with the default API vesion
        mocker.get(
            f"{self.base_url}/{client.default_version}/cards/test-card/", json={"id": "test-card"}
        )

        response = client.get_card_detail("test-card")
        self.assertEqual(response, {"id": "test-card"})

    @requests_mock.Mocker()
    def test_card_client_adds_default_base_url(self, mocker):
        """
        Test that the card client includes the default base url

        """
        # setup a client with no base url
        client = CardClient({})

        # setup a request mock for a card detail request with the default api version
        mocker.get(
            f"https://api.apps.cam.ac.uk/card/{client.default_version}/cards/any-card/",
            json={"id": "any-card"},
        )

        # check that the mock request path was hit
        response = client.get_card_detail("any-card")
        self.assertEqual(response, {"id": "any-card"})


class TestGetCardsByIds(TestCase, CardAPITestMixin):
    mocked_cards = [
        {"id": "card-1", "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}]},
        {"id": "card-2", "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}]},
        {"id": "card-3", "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}]},
    ]

    @requests_mock.Mocker()
    def test_card_cards_by_id_gives_an_iterator_of_each_card(self, mocker):
        """
        Sanity test that the client can get cards by identifier - calling the correct
        endpoint and returning the identifiers as an iterator.
        """

        client = self.make_client()
        adapter = mocker.post(
            self.api_url("/cards/filter/?page_size=500"),
            json={
                "results": TestGetCardsByIds.mocked_cards,
            },
        )

        result = list(client.cards_for_identifiers(["wgd23", "rjg21"]))
        self.assertListEqual(result, TestGetCardsByIds.mocked_cards)

        # check that the identifiers were sent in the request
        self.assertEqual(adapter.last_request.json(), {"identifiers": ["wgd23", "rjg21"]})

    @requests_mock.Mocker()
    def test_page_size_is_honored_and_pages_followed(self, mocker):
        """
        Test that the client sends the page size as setup in __init__
        and that pages are followed when a paged response is given

        """
        client = self.make_client({"page_size": 1})
        initial_post = mocker.post(
            self.api_url("/cards/filter/?page_size=1"),
            json={
                "results": [TestGetCardsByIds.mocked_cards[0]],
                "next": self.api_url("/cards/filter/?cursor=cD0yMDIxL"),
            },
        )
        page_two_post = mocker.post(
            self.api_url("/cards/filter/?cursor=cD0yMDIxL"),
            json={
                "results": [TestGetCardsByIds.mocked_cards[1]],
                "next": self.api_url("/cards/filter/?cursor=efSx21sf3L"),
            },
        )
        page_three_post = mocker.post(
            self.api_url("/cards/filter/?cursor=efSx21sf3L"),
            json={"results": [TestGetCardsByIds.mocked_cards[2]]},
        )

        result = list(client.cards_for_identifiers(["wgd23", "rjg21"]))
        self.assertListEqual(result, TestGetCardsByIds.mocked_cards)

        self.assertEqual(initial_post.call_count, 1)
        self.assertEqual(page_two_post.call_count, 1)
        self.assertEqual(page_three_post.call_count, 1)

        # check that the identifiers were sent in the request
        self.assertEqual(initial_post.last_request.json(), {"identifiers": ["wgd23", "rjg21"]})
        # no body for followup requests
        self.assertIsNone(page_two_post.last_request.text)
        self.assertIsNone(page_three_post.last_request.text)

    @requests_mock.Mocker()
    def test_id_requests_are_chunked_and_pages_followed(self, mocker):
        """
        Test that requests for large amounts of identifiers are chunked
        and that any paged responses are followed for these chunks

        """
        # create 55 ids, which is over the default chunk size for the number of ids that
        # will be sent with one request
        ids = [f"aa{index}" for index in range(55)]
        client = self.make_client()

        chunk_posts = mocker.post(
            self.api_url("/cards/filter/?page_size=500"),
            [
                {
                    # initial post for the first chunk of ids - gives a 'next' link which should be
                    # followed
                    "json": {
                        "results": [TestGetCardsByIds.mocked_cards[0]],
                        "next": self.api_url("/cards/filter/?cursor=aE02sMDIALx9"),
                    }
                },
                {
                    # the second post for the last chunk of ids
                    "json": {"results": [TestGetCardsByIds.mocked_cards[2]]}
                },
            ],
        )

        # the request to get the second page from the initial response
        chunk_one_paged_post = mocker.post(
            self.api_url("/cards/filter/?cursor=aE02sMDIALx9"),
            json={
                "results": [TestGetCardsByIds.mocked_cards[1]],
            },
        )

        result = list(client.cards_for_identifiers(ids))
        self.assertListEqual(result, TestGetCardsByIds.mocked_cards)

        # check that two chunked requests were made and the number of identifers sent in
        # each request was 50 and 5.
        self.assertEqual(len(chunk_posts.request_history), 2)
        self.assertEqual(chunk_posts.request_history[0].json(), {"identifiers": ids[:50]})
        self.assertEqual(chunk_posts.request_history[1].json(), {"identifiers": ids[50:]})

        # check that the page request was made without any body
        self.assertIsNone(chunk_one_paged_post.last_request.text)

    @requests_mock.Mocker()
    def test_id_chunk_size_can_be_amended(self, mocker):
        """
        Test that we can set a custom chunk size and id requests will be chunked by
        this size

        """
        client = self.make_client()

        # setup the request handler to respond with each id one at a time
        chunk_posts = mocker.post(
            self.api_url("/cards/filter/?page_size=500"),
            [
                {
                    "json": {
                        "results": [TestGetCardsByIds.mocked_cards[0]],
                    }
                },
                {
                    "json": {
                        "results": [TestGetCardsByIds.mocked_cards[1]],
                    }
                },
                {
                    "json": {
                        "results": [TestGetCardsByIds.mocked_cards[2]],
                    }
                },
            ],
        )

        # make a request using tiny chunk size - we should get all cards back
        result = list(client.cards_for_identifiers(["wgd23", "rjg21", "fjc55"], chunk_size=1))
        self.assertListEqual(result, TestGetCardsByIds.mocked_cards)

        # assert that three requests have been made each with a single id
        self.assertEqual(len(chunk_posts.request_history), 3)
        self.assertEqual(chunk_posts.request_history[0].json(), {"identifiers": ["wgd23"]})
        self.assertEqual(chunk_posts.request_history[1].json(), {"identifiers": ["rjg21"]})
        self.assertEqual(chunk_posts.request_history[2].json(), {"identifiers": ["fjc55"]})

    @requests_mock.Mocker()
    def test_params_are_applied_to_request(self, mocker):
        """
        Test that we can set a custom chunk size and id requests will be chunked by
        this size

        """
        client = self.make_client()

        # setup the request handler to expect additional query params - but respond with nothing
        mocker.post(self.api_url("/cards/filter/?page_size=500&status=ISSUED&key=value"), json={})

        # make a request with params - this would raise if we missed the url above
        result = list(
            client.cards_for_identifiers(["wgd23"], params={"status": "ISSUED", "key": "value"})
        )
        self.assertListEqual(result, [])


class TestGetAllCards(TestCase, CardAPITestMixin):
    mocked_cards = [
        {"id": f"card-{index}", "identifiers": [{"scheme": CRSID_SCHEME, "value": f"aab{index}"}]}
        for index in range(300)
    ]

    @requests_mock.Mocker()
    def test_all_cards_can_be_fetched_with_pages(self, mocker):
        """
        Test that all cards can be fetched and paged responses handled

        """
        client = self.make_client()

        # initial request which returns a next link
        mocker.get(
            self.api_url("/cards/?page_size=500"),
            json={
                "results": TestGetAllCards.mocked_cards[:200],
                "next": self.api_url("/cards/?cursor=agrXdw32"),
            },
        )
        # the request to get the next link
        mocker.get(
            self.api_url("/cards/?cursor=agrXdw32"),
            json={"results": TestGetAllCards.mocked_cards[200:]},
        )

        response = list(client.all_cards())

        # we should have all cards
        self.assertListEqual(response, TestGetAllCards.mocked_cards)

    @requests_mock.Mocker()
    def test_page_size_can_be_altered(self, mocker):
        """
        Test that we can set a custom page size which is used in the query params of the
        request to the Card API

        """
        client = self.make_client({"page_size": 500})

        mocker.get(
            self.api_url("/cards/?page_size=500"),
            json={
                "results": TestGetAllCards.mocked_cards,
            },
        )

        response = list(client.all_cards())

        # we should have all cards
        self.assertListEqual(response, TestGetAllCards.mocked_cards)

    @requests_mock.Mocker()
    def test_query_params_can_be_applied(self, mocker):
        """
        Test that query params can be passed into the method and applied to the query string

        """
        client = self.make_client({"page_size": 750})

        # setup the request handler to expect additional query params - but respond with nothing
        mocker.get(
            self.api_url("/cards/?page_size=750&status=REVOKED&card_type=MIFARE_TEMPORARY"),
            json={},
        )

        response = list(client.all_cards(status="REVOKED", card_type="MIFARE_TEMPORARY"))

        # we should have no cards
        self.assertListEqual(response, [])

    @requests_mock.Mocker()
    def test_failed_requests_retry(self, mocker):
        """
        Test that failed requests are retried.

        """
        client = self.make_client({})

        mocker.get(
            self.api_url("/cards/?page_size=500"),
            [
                {"status_code": 500},  # first request fails
                {"json": {"results": TestGetAllCards.mocked_cards}},  # second request works
            ],
        )

        response = list(client.all_cards())

        # we should have all cards - as the initially failing request should have been retried
        self.assertListEqual(response, TestGetAllCards.mocked_cards)

    @requests_mock.Mocker()
    def test_failed_requests_retry_configurable(self, mocker):
        """
        Test that failed requests are retried with a configurable amount of retries

        """
        client = self.make_client({"retry_attempts": 4})

        mocker.get(
            self.api_url("/cards/?page_size=500"),
            [
                {"status_code": 500},  # first request fails
                {"status_code": 500},  # second request fails
                {"status_code": 500},  # third request fails
                {"json": {"results": TestGetAllCards.mocked_cards}},  # fourth request works
            ],
        )

        response = list(client.all_cards())
        self.assertListEqual(response, TestGetAllCards.mocked_cards)

        # test the negative case - of the retry being disabled and the client throwing
        no_retry_client = self.make_client({"retry_attempts": 0})
        mocker.get(self.api_url("/cards/?page_size=500"), [{"status_code": 500}])

        with self.assertRaisesRegex(HTTPError, "500"):
            list(no_retry_client.all_cards())


class TestGetCardDetail(TestCase, CardAPITestMixin):
    @requests_mock.Mocker()
    def test_get_card_detail_returns_record(self, mocker):
        """
        Test that get card detail calls the right endpoint and returns the json from the API

        """
        client = self.make_client()
        mocker.get(
            self.api_url("/cards/test-card-id/"),
            json={
                "id": "test-card-id",
                "identifiers": [],
                "issuedAt": "2000-01-23T00:00:00Z",
                "issueNumber": 1,
                "expiresAt": "2001-01-31T00:00:00Z",
                "status": "EXPIRED",
                "cardType": "MIFARE_PERSONAL",
                "notes": [],
            },
        )

        card_detail = client.get_card_detail("test-card-id")
        self.assertEqual(
            card_detail,
            {
                "id": "test-card-id",
                "identifiers": [],
                "issuedAt": "2000-01-23T00:00:00Z",
                "issueNumber": 1,
                "expiresAt": "2001-01-31T00:00:00Z",
                "status": "EXPIRED",
                "cardType": "MIFARE_PERSONAL",
                "notes": [],
            },
        )

    @requests_mock.Mocker()
    def test_get_card_detail_errors_are_raised(self, mocker):
        """
        Test that http errors are raised if the underlying request fails

        """
        client = self.make_client()
        mocker.get(
            self.api_url("/cards/no-such-card-id/"), exc=exceptions.HTTPError("404 Not Found")
        )

        with self.assertRaises(exceptions.HTTPError):
            client.get_card_detail("no-such-card-id")


class TestLegacyCardholderClient(TestCase):
    base_url = "https://test.com/legacycardholders"

    def make_client(self, config: Optional[Mapping] = {}):
        return LegacyCardholderClient({"base_url": self.base_url, **config})

    @requests_mock.Mocker()
    def test_get_people_by_legacy_org_id(self, mocker):
        """
        Test the LegacyCard client returns users filtered by org_id

        """

        client = self.make_client()

        mocker.get(
            self.base_url,
            json={
                "lastRunTime": "2021-05-14T01:04:16.505132",
                "records": [
                    {"cam_uid": "jd0001u", "display_name": "John Doe", "org_id": [91]},
                    {"cam_uid": "jd0002u", "display_name": "Jane Doe", "org_id": [91]},
                    {"cam_uid": "jd0003u", "display_name": "Jimmy Doe", "org_id": [23]},
                ],
            },
        )

        response = client.get_people_by_legacy_org_id(ids=[91])
        self.assertEqual(
            response,
            [
                {"cam_uid": "jd0001u", "display_name": "John Doe"},
                {"cam_uid": "jd0002u", "display_name": "Jane Doe"},
            ],
        )
