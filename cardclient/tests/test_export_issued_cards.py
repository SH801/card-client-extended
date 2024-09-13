from contextlib import contextmanager
from csv import DictReader, DictWriter
from tempfile import NamedTemporaryFile
from typing import Dict, List
from unittest import TestCase, mock

from cardclient.card_client import CardClient
from cardclient.consts import DEFAULT_FIELDS
from cardclient.export_issued_cards import (
    export_issued_cards,
    update_issued_cards_export,
)
from cardclient.identifiers import CRSID_SCHEME


def card_client_with_results(results: List[Dict] = []):
    client = CardClient({"base_url": "https://test.com"})
    client.all_cards = mock.MagicMock(return_value=results)
    return client


class ExportIssuedCardsTestCase(TestCase):
    def export_to_file_and_read(self, config, card_client, *, return_columns=False):
        with NamedTemporaryFile(suffix=".csv") as temp_file:
            output_config = config.get("output", {})
            output_config["file"] = temp_file.name

            export_issued_cards({**config, "output": output_config}, card_client)

            with open(temp_file.name) as file_content:
                # convert the content back to a standard dict rather than ordered,
                # to allow for easier comparison
                reader = DictReader(file_content)
                data = [dict(data) for data in reader]

                if return_columns:
                    return (reader.fieldnames, data)
                return data

    def test_can_export_all_cards(self):
        card_response = [
            {
                "id": "123",
                "updatedAt": "2010-01-23T00:00:00Z",
                "issuedAt": "2000-01-23T00:00:00Z",
                "issueNumber": 1,
                "status": "ISSUED",
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "abc123"}],
            },
            {
                "id": "124",
                "updatedAt": "2010-02-23T00:00:00Z",
                "issuedAt": "2000-02-23T00:00:00Z",
                "issueNumber": 2,
                "status": "ISSUED",
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "abc124"}],
            },
            {
                "id": "125",
                "updatedAt": "2010-03-23T00:00:00Z",
                "issuedAt": "2000-03-23T00:00:00Z",
                "issueNumber": 3,
                "status": "ISSUED",
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "abc125"}],
            },
        ]

        card_client = card_client_with_results(card_response)

        # We compare against results with the blank defaults filter out,
        # as we simply want to check that the values passed back from the
        # card client get written. We test that default columns are included
        # below.
        results = self.export_to_file_and_read({}, card_client)
        results_without_blank_fields = list(
            map(
                lambda result: {key: value for key, value in result.items() if value != ""},
                results,
            )
        )

        card_client.all_cards.assert_called_once_with(status="ISSUED", card_type="MIFARE_PERSONAL")
        self.assertListEqual(
            results_without_blank_fields,
            [
                {
                    "id": "123",
                    "crsid": "abc123",
                    "status": "ISSUED",
                    "updatedAt": "2010-01-23T00:00:00Z",
                    "issueNumber": "1",
                    "issuedAt": "2000-01-23T00:00:00Z",
                },
                {
                    "id": "124",
                    "crsid": "abc124",
                    "status": "ISSUED",
                    "updatedAt": "2010-02-23T00:00:00Z",
                    "issueNumber": "2",
                    "issuedAt": "2000-02-23T00:00:00Z",
                },
                {
                    "id": "125",
                    "crsid": "abc125",
                    "status": "ISSUED",
                    "updatedAt": "2010-03-23T00:00:00Z",
                    "issueNumber": "3",
                    "issuedAt": "2000-03-23T00:00:00Z",
                },
            ],
        )

    def test_export_uses_field_names_in_config(self):
        card_response = [
            {
                "id": "1",
                "updatedAt": "2010-01-23T00:00:00Z",
                "issuedAt": "2000-01-23T00:00:00Z",
                "issueNumber": 1,
                "status": "ISSUED",
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "aa11"}],
            }
        ]

        card_client = card_client_with_results(card_response)

        # initially ensure that all default fields are included
        self.assertListEqual(
            self.export_to_file_and_read({}, card_client),
            [
                {
                    "surname": "",
                    "mifare_id": "",
                    "legacy_card_holder_id": "",
                    "id": "1",
                    "forenames": "",
                    "expiresAt": "",
                    "returnedAt": "",
                    "visible_name": "",
                    "issueNumber": "1",
                    "issuedAt": "2000-01-23T00:00:00Z",
                    "status": "ISSUED",
                    "photo_id": "",
                    "mifare_number": "",
                    "usn": "",
                    "updatedAt": "2010-01-23T00:00:00Z",
                    "crsid": "aa11",
                    "revokedAt": "",
                    "legacy_card_id": "",
                    "staff_number": "",
                    "cardType": "",
                    "mifare_id_hex": "",
                    "barcode": "",
                    "bgs_id": "",
                    "affiliation_status": "",
                }
            ],
        )

        # then check that we can limit using 'fields' - including fields that don't exist
        config = {"output": {"fields": ["crsid", "issuedAt", "test"]}}
        self.assertListEqual(
            self.export_to_file_and_read(config, card_client),
            [
                {
                    "crsid": "aa11",
                    # id and updated at are always included to allow incremental updates
                    "id": "1",
                    "issuedAt": "2000-01-23T00:00:00Z",
                    "test": "",
                    "updatedAt": "2010-01-23T00:00:00Z",
                }
            ],
        )

    def test_ordering_of_columns_is_consistent_in_csvs(self):
        card_response = [
            {
                "id": "1",
                "updatedAt": "2010-01-23T00:00:00Z",
                "issuedAt": "2000-01-23T00:00:00Z",
                "issueNumber": 1,
                "status": "ISSUED",
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "aa11"}],
                "unexpectedField": "Unexpected",
            }
        ]
        card_client = card_client_with_results(card_response)

        # when we don't specify the fields we should get the default fields with any extra
        # fields included on the card at the end
        (columns, _) = self.export_to_file_and_read({}, card_client, return_columns=True)
        self.assertListEqual(columns, DEFAULT_FIELDS + ["unexpectedField"])

        # when we specify the fields to include we should get them back in the order that
        # has been specified in the config - with id and updatedAt included at the end
        config = {"output": {"fields": ["random_field", "mifare_id", "crsid"]}}
        (columns, _) = self.export_to_file_and_read(config, card_client, return_columns=True)
        self.assertListEqual(columns, ["random_field", "mifare_id", "crsid", "id", "updatedAt"])

    def test_export_copes_with_no_results(self):
        self.assertListEqual(self.export_to_file_and_read({}, card_client_with_results([])), [])


class IncrementalIssuedCardsExportTestCase(TestCase):
    @contextmanager
    def existing_export(self, records):
        with NamedTemporaryFile(suffix=".csv") as temp_file:
            with open(temp_file.name, "w") as file:
                writer = DictWriter(file, records[0].keys() if records else [])
                writer.writeheader()
                writer.writerows(records)
                file.flush()

                yield temp_file.name

    def incrementally_updated_and_read(self, export_file_name, config, card_client):
        output_config = config.get("output", {})
        output_config["file"] = export_file_name

        update_issued_cards_export({**config, "output": output_config}, card_client)

        with open(export_file_name, "r") as file_content:
            # convert the content back to a standard dict rather than ordered,
            # to allow for easier comparison
            return [dict(data) for data in DictReader(file_content)]

    def test_can_incrementally_update_an_export(self):
        starting_records = [
            {
                "id": "122",  # should not change
                "status": "ISSUED",
                "issuedAt": "2021-05-23T00:00:00Z",
                "updatedAt": "2021-05-23T00:00:00Z",
                "crsid": "aa112",
            },
            {
                "id": "123",
                "status": "ISSUED",
                "issuedAt": "2020-01-23T00:00:00Z",
                "updatedAt": "2021-01-23T00:00:00Z",
                "crsid": "ab123",
            },
            {
                "id": "124",
                "status": "ISSUED",
                "issuedAt": "2021-01-23T00:00:00Z",
                "updatedAt": "2021-06-23T00:00:00Z",
                "crsid": "ab124",
            },
        ]

        updated_records = [
            {
                "id": "123",
                "status": "ISSUED",
                "issuedAt": "2020-01-23T00:00:00Z",
                "updatedAt": "2021-07-23T00:00:00Z",
                "identifiers": [
                    {"scheme": CRSID_SCHEME, "value": "xxx99"}
                ],  # should cause an update
            },
            {
                "id": "124",
                "status": "REVOKED",  # should cause this card to be removed
                "issuedAt": "2021-01-23T00:00:00Z",
                "updatedAt": "2021-07-23T00:00:00Z",
            },
            {
                "id": "125",  # should add this card
                "status": "ISSUED",
                "issuedAt": "2021-07-23T00:00:00Z",
                "updatedAt": "2021-07-23T00:00:00Z",
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "zzz99"}],
            },
        ]

        card_client = card_client_with_results(updated_records)

        with self.existing_export(starting_records) as existing_export:
            result = self.incrementally_updated_and_read(existing_export, {}, card_client)

            # the card client should have been queried with the highest updated_at
            # from the initial export
            card_client.all_cards.assert_called_once_with(
                updated_at__gte="2021-06-23T00:00:00", card_type="MIFARE_PERSONAL"
            )

            self.assertListEqual(
                result,
                [
                    {
                        "crsid": "aa112",  # no change expected
                        "id": "122",
                        "issuedAt": "2021-05-23T00:00:00Z",
                        "updatedAt": "2021-05-23T00:00:00Z",
                        "status": "ISSUED",
                    },
                    {
                        "crsid": "xxx99",  # crsid is updated from card client
                        "id": "123",
                        "issuedAt": "2020-01-23T00:00:00Z",
                        "status": "ISSUED",
                        "updatedAt": "2021-07-23T00:00:00Z",
                    },
                    {
                        "crsid": "zzz99",
                        "id": "125",  # new card added to export
                        "issuedAt": "2021-07-23T00:00:00Z",
                        "status": "ISSUED",
                        "updatedAt": "2021-07-23T00:00:00Z",
                    },
                ],
            )

    def test_incremental_export_uses_field_from_initial_export(self):
        starting_records = [
            {
                "id": "100",
                "status": "ISSUED",
                "issuedAt": "2021-06-30T12:10:00Z",
                "updatedAt": "2021-06-30T12:10:00Z",
                "crsid": "bb123",
                "test": "",
            }
        ]

        updated_records = [
            {
                "id": "100",
                "status": "ISSUED",
                "issuedAt": "2021-06-30T12:10:00Z",
                "updatedAt": "2021-07-23T00:00:00Z",
                "cardType": "MIFARE_PERSONAL",  # additional fields which should not be included
                "issueNumber": 1,  # as they do not exist in the initial export
                "identifiers": [{"scheme": CRSID_SCHEME, "value": "xxx90"}],  # should update
            }
        ]

        card_client = card_client_with_results(updated_records)

        with self.existing_export(starting_records) as existing_export:
            result = self.incrementally_updated_and_read(existing_export, {}, card_client)

            card_client.all_cards.assert_called_once_with(
                updated_at__gte="2021-06-30T12:10:00", card_type="MIFARE_PERSONAL"
            )

            # we expect the result to use the same field names as in the original export
            self.assertEqual(
                result,
                [
                    {
                        "crsid": "xxx90",
                        "id": "100",
                        "issuedAt": "2021-06-30T12:10:00Z",
                        "status": "ISSUED",
                        "test": "",
                        "updatedAt": "2021-07-23T00:00:00Z",
                    }
                ],
            )

    def test_incremental_update_fails_with_no_updated_at_or_id(self):
        card_client = card_client_with_results([])

        no_updated_at_export = [
            {
                "id": "99",
                "status": "ISSUED",
                "issuedAt": "2021-06-30T12:10:00Z",
                "crsid": "bb123",
            }
        ]

        no_id_export = [
            {
                "status": "ISSUED",
                "issuedAt": "2021-06-30T12:10:00Z",
                "updatedAt": "2021-06-30T12:10:00Z",
                "crsid": "bb123",
                "test": "",
            }
        ]

        with self.existing_export(no_updated_at_export) as existing_export:
            with self.assertRaisesRegex(
                RuntimeError, "Unable to update export file without updatedAt and id fields"
            ):
                self.incrementally_updated_and_read(existing_export, {}, card_client)

        with self.existing_export(no_id_export) as existing_export:
            with self.assertRaisesRegex(
                RuntimeError, "Unable to update export file without updatedAt and id fields"
            ):
                self.incrementally_updated_and_read(existing_export, {}, card_client)

    def test_incremental_update_fails_with_no_existing_data(self):
        card_client = card_client_with_results([])

        with self.existing_export([]) as existing_export:
            with self.assertRaisesRegex(
                RuntimeError, "Unable to determine last update point from export"
            ):
                self.incrementally_updated_and_read(existing_export, {}, card_client)
