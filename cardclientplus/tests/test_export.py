from collections import OrderedDict
from csv import DictReader
from io import StringIO
from json import dumps
from tempfile import NamedTemporaryFile
from typing import Dict, List, Mapping
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from identitylib.identifiers import IdentifierSchemes

from ..card_client import CardClient
from ..export import export_cards, print_card_detail
from ..identifiers import CRSID_SCHEME
from ..people_client import PeopleClient


class BaseExportTest(TestCase):
    def setUp(self):
        self.noop_people_client = self.people_client_with_results()
        self.noop_card_client = self.card_client_with_results()

    def export_to_file_and_read(self, config, card_client, people_client):
        with NamedTemporaryFile(suffix=".csv") as temp_file:
            output_config = config.get("output", {})
            output_config["file"] = temp_file.name

            export_cards({**config, "output": output_config}, card_client, people_client)

            with open(temp_file.name) as file_content:
                # convert the content back to a standard dict rather than ordered,
                # to allow for easier comparison
                return [dict(data) for data in DictReader(file_content)]

    def people_client_with_results(
        self, results: Dict[str, Mapping] = {}, scheme: str = CRSID_SCHEME
    ):
        client = PeopleClient()
        client.get_people_info_for_query = MagicMock(return_value=(results, scheme))
        return client

    def card_client_with_results(self, results: List[Dict] = []):
        client = CardClient({"base_url": "https://test.com"})
        client.cards_for_identifiers = MagicMock(return_value=results)
        return client


class TestExportConfigValidation(BaseExportTest):
    def test_export_validates_queries(self):
        """
        Test that queries are validated and empty queries raises exceptions

        """
        with self.assertRaisesRegex(ValueError, expected_regex="config.queries must be non-empty"):
            export_cards({}, self.noop_card_client, self.noop_people_client)

        with self.assertRaisesRegex(ValueError, expected_regex="config.queries must be non-empty"):
            export_cards({"queries": []}, self.noop_card_client, self.noop_people_client)


class TestExportUsesPeopleAndCardClient(BaseExportTest):
    def test_export_passes_queries_to_people_client(self):
        """
        Test that queries are passed through (as separate calls) to PeopleClient

        """
        queries = [
            {"by": "lookup_institution", "id": "devops"},
            {
                "by": "lookup_group",
                "ids": ["devops-group", "secret-devops-group"],
                "extra_fields_for_results": {"a": "b", "c": 1},
            },
        ]
        export_cards({"queries": queries}, self.noop_card_client, self.noop_people_client)

        self.noop_people_client.get_people_info_for_query.assert_has_calls(
            [call(queries[0]), call(queries[1])], any_order=False
        )

    def test_export_passes_ids_from_people_client_to_card_client(self):
        """
        Test that the id keys passed back from PeopleClient are used to query CardClient

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}
        )

        export_cards({"queries": queries}, self.noop_card_client, people_client)

        self.noop_card_client.cards_for_identifiers.assert_called_with([f"wgd23@{CRSID_SCHEME}"])

    def test_export_filters_by_params_or_filter(self):
        """
        Test that the params passed in as config are passed to CardClient

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}
        )
        # filter just issued cards with issue number 1
        filter_params = {"status": "ISSUED", "issueNumber": 1}

        card_client = self.card_client_with_results(
            [
                {
                    "id": "656323f-rgerf-2124-adaa-93458d9fga98f",
                    "issuedAt": "2011-01-23T00:00:00Z",
                    "issueNumber": 1,
                    "identifiers": [],
                    "status": "ISSUED",
                },
                {
                    "id": "2346235-argdv-123124-ajo3451-aergaero4jkf",
                    "issuedAt": "2012-01-23T00:00:00Z",
                    "issueNumber": 2,
                    "identifiers": [],
                    "status": "REVOKED",
                },
                {
                    "id": "e3fodsvji24-12ffdsf-124124123-aergaerg-2afkodvjioj",
                    "issuedAt": "2013-01-23T00:00:00Z",
                    "issueNumber": 3,
                    "identifiers": [],
                    "status": "ISSUED",
                },
            ]
        )

        content_by_filter = self.export_to_file_and_read(
            {"queries": queries, "filter": filter_params}, card_client, people_client
        )

        # make sure we just get the issued card with issue number 1
        self.assertEqual(len(content_by_filter), 1)
        self.assertEqual(content_by_filter[0]["status"], "ISSUED")
        self.assertEqual(content_by_filter[0]["issueNumber"], "1")

        # check we get the same output with the filter args passed as `params`
        content_by_params = self.export_to_file_and_read(
            {"queries": queries, "params": filter_params}, card_client, people_client
        )
        self.assertListEqual(content_by_params, content_by_filter)

    def test_results_from_card_client_are_written_normalized_to_csv(self):
        """
        Test that the results from card client are written to csv

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}
        )
        card_client = self.card_client_with_results(
            [
                {
                    "id": "57167626-dc4f-4116-adaa-0aeb6c099cfb",
                    "issuedAt": "2000-01-23T00:00:00Z",
                    "issueNumber": 1,
                    "identifiers": [],
                }
            ]
        )

        content = self.export_to_file_and_read({"queries": queries}, card_client, people_client)
        self.assertListEqual(
            content,
            [
                {
                    # identifiers are included because they are added to the flattened card
                    # as part of the normalization
                    "bgs_id": "",
                    "id": "57167626-dc4f-4116-adaa-0aeb6c099cfb",
                    "forenames": "",
                    "legacy_card_holder_id": "",
                    "issueNumber": "1",
                    "expiresAt": "",
                    "usn": "",
                    "issuedAt": "2000-01-23T00:00:00Z",
                    "legacy_card_id": "",
                    "barcode": "",
                    "mifare_id_hex": "",
                    "returnedAt": "",
                    "surname": "",
                    "status": "",
                    "affiliation_status": "",
                    "mifare_number": "",
                    "staff_number": "",
                    "visible_name": "",
                    "revokedAt": "",
                    "photo_id": "",
                    "cardType": "",
                    "mifare_id": "",
                    "crsid": "",
                    "updatedAt": "",
                }
            ],
        )

    def test_results_from_card_client_are_matched_against_person_info(self):
        """
        Test that card client results are matched against person information returned
        by PeopleClient with the personal information included

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson", "extra_field": "test"}}
        )
        card_client = self.card_client_with_results(
            [
                {
                    "id": "57167626-dc4f-4116-adaa-0aeb6c099cfb",
                    "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
                }
            ]
        )

        content = self.export_to_file_and_read({"queries": queries}, card_client, people_client)

        # we should have a single record which has `name` and `extra_field` included
        # as returned from PeopleClient
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["crsid"], "wgd23")
        self.assertEqual(content[0]["name"], "Monty Dawson")
        self.assertEqual(content[0]["extra_field"], "test")

    def test_results_from_card_client_can_be_matched_against_non_case_matching_identifers(self):
        """
        Test that card client results can be matched against non crsid identifiers
        which contain no personal information

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"vee222@{IdentifierSchemes.BARCODE}": {"another_field": "test"}},
            str(IdentifierSchemes.BARCODE),
        )
        card_client = self.card_client_with_results(
            [
                {
                    "id": "matched-based-on-barcode-id",
                    "identifiers": [{"scheme": str(IdentifierSchemes.BARCODE), "value": "vee222"}],
                }
            ]
        )

        content = self.export_to_file_and_read({"queries": queries}, card_client, people_client)

        # we should have a single record which has `name` and `extra_field` included
        # as returned from PeopleClient
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["crsid"], "")
        self.assertEqual(content[0]["barcode"], "vee222")
        self.assertEqual(content[0]["another_field"], "test")

    def test_export_will_handle_multiple_queries(self):
        """
        Test that multiple queries will be passed to person client and all results
        from person client are passed to card client, with all results being output
        correctly

        """
        queries = [{"by": "lookup_institution", "id": "devops"}, {"by": "usn", id: "3000001"}]
        people_client = self.people_client_with_results()
        card_client = self.card_client_with_results()

        # mock results from person client
        people_client.get_people_info_for_query.side_effect = [
            # result one - a single result by CRSID
            ({f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson", "is_staff": True}}, CRSID_SCHEME),
            # result two - a single result by usn
            (
                {f"3000001@{IdentifierSchemes.USN}": {"is_staff": False}},
                str(IdentifierSchemes.USN),
            ),
        ]

        # mock results from card client
        card_client.cards_for_identifiers.side_effect = [
            # result one - two cards by CRSID
            [
                {
                    "id": "matched-based-on-crsid",
                    "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
                },
                {
                    # This should never really happen - but is the case where we've queried
                    # the Card API by CRSID and it's included a card with a different
                    # CRSID - we're testing that the card is included in the export but
                    # without any personal information
                    "id": "mistakenly-included-card",
                    "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd99"}],
                },
            ],
            # result two - a single card by usn
            [
                {
                    "id": "a-student-card",
                    "identifiers": [
                        {"scheme": str(IdentifierSchemes.USN), "value": "3000001"},
                        {"scheme": CRSID_SCHEME, "value": "abb22"},
                    ],
                }
            ],
        ]

        content = self.export_to_file_and_read({"queries": queries}, card_client, people_client)

        # we should have all three cards
        self.assertEqual(len(content), 3)

        self.assertEqual(content[0]["id"], "matched-based-on-crsid")
        self.assertEqual(content[0]["crsid"], "wgd23")
        self.assertEqual(content[0]["name"], "Monty Dawson")
        self.assertEqual(content[0]["is_staff"], "True")

        # second card should not have any personal information
        self.assertEqual(content[1]["id"], "mistakenly-included-card")
        self.assertEqual(content[1]["crsid"], "wgd99")
        self.assertEqual(content[1]["name"], "")
        self.assertEqual(content[1]["is_staff"], "")

        # third card should have matched on usn
        self.assertEqual(content[2]["id"], "a-student-card")
        # the card contains the crsid, and is included in the result
        self.assertEqual(content[2]["crsid"], "abb22")
        self.assertEqual(content[2]["usn"], "3000001")
        self.assertEqual(content[2]["name"], "")  # not included in data from PersonClient
        self.assertEqual(content[2]["is_staff"], "False")


class TestExportFormatConfigurationOptions(BaseExportTest):
    def test_exports_can_be_deduplicated(self):
        """
        Test that exports can be de-duplicated based on the deduplicate flag

        """
        # setup two queries which will return the same data
        queries = [{"by": "lookup_institution", "id": "devops"}, {"by": "crsid", id: "wgd23"}]

        people_client = self.people_client_with_results()
        card_client = self.card_client_with_results()

        def set_results_for_clients():
            # mock results from person client - both queries return the same person
            people_client.get_people_info_for_query.side_effect = [
                ({f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}, CRSID_SCHEME),
                ({f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}, CRSID_SCHEME),
            ]

            # card client returns the same card for both queries
            card_client.cards_for_identifiers.side_effect = [
                [
                    {
                        "id": "matched-based-on-crsid",
                        "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
                    }
                ],
                [
                    {
                        "id": "matched-based-on-crsid",
                        "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
                    }
                ],
            ]

        # setup the clients
        set_results_for_clients()

        with_dupes = self.export_to_file_and_read({"queries": queries}, card_client, people_client)

        # the export should contain two identical cards
        self.assertEqual(len(with_dupes), 2)
        self.assertEqual(with_dupes[0], with_dupes[1])
        self.assertEqual(with_dupes[0]["crsid"], "wgd23")

        # reset the clients
        set_results_for_clients()

        # run the same export but with the deduplicate flag set
        de_duped = self.export_to_file_and_read(
            {"queries": queries, "output": {"deduplicate": True}}, card_client, people_client
        )

        # the export should contain only one card, matching the first card of the previous export
        self.assertEqual(len(de_duped), 1)
        self.assertEqual(de_duped[0], with_dupes[0])

    def test_field_names_can_be_customized(self):
        """
        Test that the field names in the export csv can be specified

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}
        )
        card_client = self.card_client_with_results(
            [
                {
                    "id": "57167626-dc4f-4116-adaa-0aeb6c099cfb",
                    "issuedAt": "2000-01-23T00:00:00Z",
                    "revokedAt": "2000-01-23T00:00:00Z",
                    "issueNumber": 1,
                    "identifiers": [
                        {
                            "scheme": CRSID_SCHEME,
                            "value": "wgd23",
                        },
                        {"scheme": str(IdentifierSchemes.LEGACY_CARDHOLDER), "value": "wg222a"},
                    ],
                }
            ]
        )
        # set specific fields, including a field that doesn't exist in the data from the
        # card or person client
        fields = ["usn", "id", "name", "something_random", "crsid", "legacy_card_holder_id"]

        content = self.export_to_file_and_read(
            {"queries": queries, "output": {"fields": fields}}, card_client, people_client
        )

        # Use ordered dict to check that order of fields matches what's specified above
        self.assertListEqual(
            content,
            [
                OrderedDict(
                    [
                        ("usn", ""),
                        ("id", "57167626-dc4f-4116-adaa-0aeb6c099cfb"),
                        ("name", "Monty Dawson"),
                        ("something_random", ""),
                        ("crsid", "wgd23"),
                        ("legacy_card_holder_id", "wg222a"),
                    ]
                )
            ],
        )


class TestExportProgressReporting(BaseExportTest):
    @patch("cardclientplus.export.Bar")
    def test_export_progress_is_shown(self, mock_progress_bar):
        """
        Basic test to ensure that the progress bar is handled correctly

        """

        queries = [{"by": "lookup_institution", "id": "devops"}]
        people_client = self.people_client_with_results(
            {f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"}}
        )
        card_client = self.card_client_with_results(
            [
                {
                    "id": "card-id",
                    "identifiers": [
                        {
                            "scheme": CRSID_SCHEME,
                            "value": "wgd23",
                        }
                    ],
                }
            ]
        )
        export_cards({"queries": queries}, card_client, people_client)

        # assert that the bar was created with the correct max value (1)
        mock_progress_bar.assert_called_once_with("   Fetching cards", max=1)
        bar_instance = mock_progress_bar.return_value

        # assert that the bar is moved to 1 (this happens twice as there is a fallback
        # to ensure that once cards are fetched the progress bar is shown to have ended)
        # and finish is then called
        bar_instance.goto.assert_has_calls([call(1), call(1)])
        bar_instance.finish.assert_called_once()

    @patch("cardclientplus.export.Bar")
    def test_progress_bar_ends_without_cards(self, mock_progress_bar):
        """
        Test that even if no cards are returned the progress bar shows as complete

        """

        queries = [{"by": "lookup_institution", "id": "devops"}]

        # the people client returns 3 people to get cards for
        people_client = self.people_client_with_results(
            {
                f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"},
                f"fjc55@{CRSID_SCHEME}": {"name": "Joe Bloggs"},
                f"rjg21@{CRSID_SCHEME}": {"name": "Bill Gates"},
            }
        )
        # but the card client doesn't return any cards
        card_client = self.card_client_with_results([])
        export_cards({"queries": queries}, card_client, people_client)

        # assert that the bar was created with the correct max value (3)
        # as we have 3 people to get cards for
        mock_progress_bar.assert_called_once_with("   Fetching cards", max=3)
        bar_instance = mock_progress_bar.return_value

        # assert that the bar is moved to 3 - we don't get any progress before this
        # as no cards are fetched, but we know that we have fetched all available
        # cards for the people returned from people client.
        bar_instance.goto.assert_has_calls([call(3)])
        bar_instance.finish.assert_called_once()

    @patch("cardclientplus.export.Bar")
    def test_progress_bar_does_not_go_past_max(self, mock_progress_bar):
        """
        Test that if multiple cards are returned for people the progress bar
        only advances when we have a card for a person we didn't previously
        have a card for. This stops the progress bar advancing past the max
        set based on the number of people returned from people client.

        """

        queries = [{"by": "lookup_institution", "id": "devops"}]

        # the people client returns 2 people to get cards for
        people_client = self.people_client_with_results(
            {
                f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"},
                f"fjc55@{CRSID_SCHEME}": {"name": "Joe Bloggs"},
            }
        )
        # the card client will return 3 cards for wgd23 but none for fjc55
        card_client = self.card_client_with_results(
            [
                {
                    "id": "card-id-1",
                    "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
                },
                {"id": "card-id-2", "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}]},
                {"id": "card-id-3", "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}]},
            ]
        )
        export_cards({"queries": queries}, card_client, people_client)

        # assert that the bar was created with the correct max value (2)
        # as we have 2 people to get cards for
        mock_progress_bar.assert_called_once_with("   Fetching cards", max=2)
        bar_instance = mock_progress_bar.return_value

        # assert that the bar is moved to 1 three times (as the first three
        # cards are returned and marked against wgd23) and then moved to 2
        # once the card api has given all results (as we want to show that
        # we have found all cards the Card API has for these people),
        # Importantly the progress bar is never moved to 3, even though we
        # have 3 cards returned from the Card API.
        bar_instance.goto.assert_has_calls([call(1), call(1), call(1), call(2)], any_order=False)
        bar_instance.finish.assert_called_once()

    @patch("cardclientplus.export.Bar")
    def test_progress_is_not_shown_if_silent_arg_passed(self, mock_progress_bar):
        """
        Ensure that if `silent` is set no progress is shown

        """
        queries = [{"by": "lookup_institution", "id": "devops"}]

        people_client = self.people_client_with_results(
            {
                f"wgd23@{CRSID_SCHEME}": {"name": "Monty Dawson"},
            }
        )
        card_client = self.card_client_with_results(
            [
                {
                    "id": "card-id-1",
                    "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
                }
            ]
        )

        export_cards({"queries": queries}, card_client, people_client, silent=True)
        mock_progress_bar.assert_not_called()


class TestPrintCardDetail(BaseExportTest):
    card_detail = {
        "id": "card-id",
        "issuedAt": "2000-01-23T00:00:00Z",
        "status": "EXPIRED",
        "identifiers": [{"scheme": CRSID_SCHEME, "value": "wgd23"}],
    }

    def setUp(self):
        super().setUp()
        self.people_client = PeopleClient()
        self.card_client = CardClient({"base_url": "https://card-api.com"})

    def test_print_card_detail_prints_result_from_card_client(self):
        self.card_client.get_card_detail = MagicMock(return_value=self.card_detail)

        with patch("sys.stdout", new=StringIO()) as mocked_print:
            print_card_detail(self.card_client, "card-id")
            self.assertEqual(mocked_print.getvalue().strip(), dumps([self.card_detail], indent=4))

    def test_print_card_detail_can_normalize_json(self):
        self.card_client.get_card_detail = MagicMock(return_value=self.card_detail)

        normalized_detail = CardClient.normalize_card(self.card_detail)

        with patch("sys.stdout", new=StringIO()) as mocked_print:
            print_card_detail(self.card_client, "card-id", None, True)
            self.assertEqual(mocked_print.getvalue().strip(), dumps([normalized_detail], indent=4))

    def test_print_card_detail_allows_querying_by_id_scheme(self):
        self.card_client.cards_for_identifiers = MagicMock(return_value=[{"id": "123-abc"}])
        self.card_client.get_card_detail = MagicMock(return_value=self.card_detail)

        with patch("sys.stdout", new=StringIO()) as mocked_print:
            print_card_detail(self.card_client, "wgd23", "crsid")
            self.assertEqual(mocked_print.getvalue().strip(), dumps([self.card_detail], indent=4))

            # check that we first query for cards based on the identifier scheme provided
            # and we then query for the card detail using the id returned
            self.card_client.cards_for_identifiers.assert_called_once_with(
                [f"wgd23@{CRSID_SCHEME}"]
            )
            self.card_client.get_card_detail.assert_called_once_with("123-abc")

    def test_print_card_detail_throws_if_no_cards_for_id(self):
        self.card_client.cards_for_identifiers = MagicMock(return_value=[])

        with self.assertRaisesRegex(ValueError, "No card records for crsid abc"):
            print_card_detail(self.card_client, "abc", "crsid")

    def test_print_card_detail_throws_if_provided_bad_scheme(self):
        self.card_client.cards_for_identifiers = MagicMock(return_value=[])

        with self.assertRaisesRegex(
            ValueError, "bad-scheme not a recognized id scheme, must be one of: "
        ):
            print_card_detail(self.card_client, "123", "bad-scheme")
