from unittest import TestCase, mock

from identitylib.identifiers import Identifier, IdentifierSchemes

from cardclient.tests.mocks import (
    MockedLegacyCardholderClient,
    create_people_client_with_ibis_mocked,
)

from ..hr_client import UniversityHRClient
from ..identifiers import CRSID_SCHEME, identifier_names, identifier_names_to_schemes
from ..people_client import PeopleClient
from ..student_client import UniversityStudentClient


class TestPeopleClientCredentials(TestCase):
    def test_people_client_uses_lookup_credentials_from_config(self):
        """
        Test that lookup credentials are applied only if both username and password are present

        """

        client_without_credentials = PeopleClient()
        self.assertEqual(client_without_credentials.ibis_connection.username, "anonymous")
        self.assertIsNone(client_without_credentials.ibis_connection.password)

        client_with_credentials = PeopleClient({"username": "test", "password": "test_password"})
        self.assertEqual(client_with_credentials.ibis_connection.username, "test")
        self.assertEqual(client_with_credentials.ibis_connection.password, "test_password")

        client_with_bad_credentials = PeopleClient(
            {"user": "test", "password": "test_password"}  # should be 'username'
        )

        # neither is set within the connection created in the client
        self.assertEqual(client_with_bad_credentials.ibis_connection.username, "anonymous")
        self.assertIsNone(client_with_bad_credentials.ibis_connection.password)


class TestPeopleClientQueryValidation(TestCase):
    def test_query_ids_are_validated(self):
        """
        Test that the `id` or `ids` on a query are validated

        """

        client = PeopleClient()

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query does not contain an id or list of ids: "
        ):
            client.get_people_info_for_query({"by": "usn"})

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query does not contain an id or list of ids: "
        ):
            client.get_people_info_for_query({"id": "", "by": "usn"})

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query does not contain an id or list of ids: "
        ):
            client.get_people_info_for_query({"ids": [], "by": "usn"})

        # these should both be fine
        client.get_people_info_for_query({"id": "3000001", "by": "usn"})
        client.get_people_info_for_query({"ids": ["300001"], "by": "usn"})

    def test_lql_query_is_validated(self):
        """
        Test that queries by `lql` are enforced to have a `lql_query` attribute

        """

        client = PeopleClient()

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query by lql must contain a string `lql_query` attribute"
        ):
            client.get_people_info_for_query({"by": "lql"})

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query by lql must contain a string `lql_query` attribute"
        ):
            client.get_people_info_for_query({"by": "lql", "id": "1"})

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query by lql must contain a string `lql_query` attribute"
        ):
            client.get_people_info_for_query({"by": "lql", "lql_query": ""})

        with self.assertRaisesRegex(
            ValueError, expected_regex="Query by lql must contain a string `lql_query` attribute"
        ):
            client.get_people_info_for_query({"by": "lql", "lql_query": ['crsid = "wgd23"']})

        # create a people client with the Ibis method mocked, otherwise this will actually
        # try to call Lookup
        client_with_mocked_ibis_backend = create_people_client_with_ibis_mocked()

        # this should be valid
        client_with_mocked_ibis_backend.get_people_info_for_query(
            {"by": "lql", "lql_query": 'crsid = "wgd23"'}
        )

    def test_query_by_is_validated(self):
        """
        Test that the `by` property on a query is validated and only known values are allowed

        """

        client = PeopleClient()

        with self.assertRaisesRegex(
            ValueError, expected_regex=r"Invalid `by` field on query, available options are \[.*\]"
        ):
            client.get_people_info_for_query({"id": "1"})

        with self.assertRaisesRegex(
            ValueError, expected_regex="Invalid `by` field on query, available options are"
        ):
            client.get_people_info_for_query({"id": "1", "by": "something_random"})

        client_with_mocked_ibis_backend = create_people_client_with_ibis_mocked()
        valid_bys = list(identifier_names) + ["lookup_institution", "lookup_group"]
        for by in valid_bys:
            # all should work without error
            client_with_mocked_ibis_backend.get_people_info_for_query({"id": "1", "by": by})


class TestPeopleClientLookupQueries(TestCase):
    def test_lookup_institutions_can_be_queried(self):
        """
        Test that Lookup institutions can be queried and the result parsed

        """

        def ibis_call_mock(method, args):
            self.assertEqual(method, "inst_get_members")
            self.assertEqual(
                args, ("devops_inst", "visibleName,surname,firstName,all_identifiers")
            )
            return [
                {
                    "visible_name": "Monty Dawson",
                    "identifiers": [{"scheme": "crsid", "value": "wgd23"}],
                    "attributes": [{"scheme": "firstName", "value": "Monty"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)

        (parsed_result, scheme) = client.get_people_info_for_query(
            {"id": "devops_inst", "by": "lookup_institution"}
        )

        self.assertEqual(scheme, CRSID_SCHEME)
        self.assertEqual(
            parsed_result,
            {
                f"wgd23@{CRSID_SCHEME}": {
                    "visible_name": "Monty Dawson",
                    "surname": None,
                    "forenames": "Monty",
                }
            },
        )

    def test_lookup_groups_can_be_queried(self):
        """
        Test that Lookup groups can be queried and the result parsed

        """

        def ibis_call_mock(method, args):
            self.assertEqual(method, "group_get_members")
            self.assertEqual(
                args, ("devops_group", "visibleName,surname,firstName,all_identifiers")
            )
            return [
                {
                    "visible_name": "Joe Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "fjc55"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)

        (parsed_result, scheme) = client.get_people_info_for_query(
            {"id": "devops_group", "by": "lookup_group"}
        )

        self.assertEqual(scheme, CRSID_SCHEME)
        self.assertEqual(
            parsed_result,
            {
                f"fjc55@{CRSID_SCHEME}": {
                    "visible_name": "Joe Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                }
            },
        )

    def test_lookup_can_be_queried_by_crsid(self):
        """
        Test that Lookup can be queried by crsid and the result parsed

        """

        def ibis_call_mock(method, args):
            self.assertEqual(method, "person_list_people")
            self.assertEqual(args, ("wgd23", "visibleName,surname,firstName,all_identifiers"))
            return [
                {
                    "visible_name": "Monty Dawson",
                    "identifiers": [{"scheme": "crsid", "value": "wgd23"}],
                    "attributes": [{"scheme": "firstName", "value": "Monty"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)

        (parsed_result, scheme) = client.get_people_info_for_query({"id": "wgd23", "by": "crsid"})

        self.assertEqual(scheme, CRSID_SCHEME)
        self.assertEqual(
            parsed_result,
            {
                f"wgd23@{CRSID_SCHEME}": {
                    "visible_name": "Monty Dawson",
                    "surname": None,
                    "forenames": "Monty",
                }
            },
        )

    def test_inst_and_group_queries_can_be_made_for_multiple_ids(self):
        """
        Test that inst and group queries can be made with multiple ids - with multiple requests
        being made to Lookup
        The code is shared, so just exercise the inst query

        """
        calls_to_lookup = []

        def ibis_call_mock(method, args):
            calls_to_lookup.append(args)

            if len(calls_to_lookup) == 1:
                return [
                    {
                        "visible_name": "Joe Bloggs",
                        "identifiers": [{"scheme": "crsid", "value": "fjc55"}],
                        "attributes": [{"scheme": "firstName", "value": "Joe"}],
                    }
                ]

            return [
                {
                    "visible_name": "John Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "rjg21"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)
        (parsed_result, _) = client.get_people_info_for_query(
            {"ids": ["devops", "secret_devops"], "by": "lookup_institution"}
        )

        self.assertListEqual(
            calls_to_lookup,
            [
                ("devops", "visibleName,surname,firstName,all_identifiers"),
                ("secret_devops", "visibleName,surname,firstName,all_identifiers"),
            ],
        )
        self.assertEqual(
            parsed_result,
            {
                f"fjc55@{CRSID_SCHEME}": {
                    "visible_name": "Joe Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                },
                f"rjg21@{CRSID_SCHEME}": {
                    "visible_name": "John Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                },
            },
        )

    def test_querying_lookup_by_lots_of_crsids_chunks_requests(self):
        """
        Test that multiple chunked requests are made when over 100 crsids are queried by

        """
        crsids_to_query_by = [f"wgd{index}" for index in range(100)] + ["wgd99"]
        calls_to_lookup = []

        def ibis_call_mock(method, args):
            self.assertEqual(method, "person_list_people")
            calls_to_lookup.append(args)

            if len(calls_to_lookup) == 1:
                return [
                    {
                        "visible_name": f"Joe Bloggs {index}",
                        "identifiers": [{"scheme": "crsid", "value": f"wgd{index}"}],
                        "attributes": [{"scheme": "firstName", "value": "Joe"}],
                    }
                    for index in range(100)
                ]

            return [
                {
                    "visible_name": "John Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "wgd99"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)
        (parsed_result, _) = client.get_people_info_for_query(
            {"ids": crsids_to_query_by, "by": "crsid"}
        )

        self.assertEqual(len(calls_to_lookup), 2)
        # check that the initial call got the first 100 ids, and the second call got the 101st
        self.assertEqual(calls_to_lookup[0][0], ",".join(crsids_to_query_by[:100]))
        self.assertEqual(calls_to_lookup[1][0], ",".join(crsids_to_query_by[100:101]))

        for crsid in crsids_to_query_by:
            self.assertIn(f"{crsid}@{CRSID_SCHEME}", parsed_result.keys())

    def test_inst_and_group_query_handles_multiple_results(self):
        """
        Test that inst and group queries can parse multiple results.
        The code is shared, so just exercise the inst query

        """

        def ibis_call_mock(method, args):
            return [
                {
                    "visible_name": "Joe Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "rjg21"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                },
                {
                    "visible_name": "John Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "fjc55"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                },
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)
        (parsed_result, _) = client.get_people_info_for_query(
            {"id": "devops", "by": "lookup_institution"}
        )

        self.assertEqual(
            parsed_result,
            {
                f"rjg21@{CRSID_SCHEME}": {
                    "visible_name": "Joe Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                },
                f"fjc55@{CRSID_SCHEME}": {
                    "visible_name": "John Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                },
            },
        )

    def test_extra_fields_get_applied_to_lookup_results(self):
        """
        Test that the extra fields on a query get applied to the results
        The code is shared, so just exercise the group query

        """

        def ibis_call_mock(method, args):
            return [
                {
                    "visible_name": "Joe Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "rjg21"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                },
                {
                    "visible_name": "John Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "fjc55"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                },
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)
        (parsed_result, _) = client.get_people_info_for_query(
            {
                "id": "devops_group",
                "by": "lookup_group",
                "extra_fields_for_results": {"a": "b", "c": 1},
            }
        )

        self.assertEqual(
            parsed_result,
            {
                f"rjg21@{CRSID_SCHEME}": {
                    "visible_name": "Joe Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                    "a": "b",
                    "c": 1,
                },
                f"fjc55@{CRSID_SCHEME}": {
                    "visible_name": "John Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                    "a": "b",
                    "c": 1,
                },
            },
        )

    def test_queries_to_lookup_always_return_lowercase_identifiers(self):
        """
        Test that identifiers are always coerced into lowercase even if returned uppercase from
        Lookup.
        The code is shared, so just exercise the crsid query

        """

        def ibis_call_mock(method, args):
            return [
                {
                    "visible_name": "Joe Bloggs",
                    "identifiers": [{"scheme": "crsid", "value": "RJG21"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)
        (parsed_result, _) = client.get_people_info_for_query({"id": "rjg21", "by": "crsid"})

        self.assertEqual(
            parsed_result,
            {
                f"rjg21@{CRSID_SCHEME}": {
                    "visible_name": "Joe Bloggs",
                    "surname": None,
                    "forenames": "Joe",
                },
            },
        )

    def test_results_from_lookup_without_crsid_are_not_appended(self):
        """
        Test that only people returned from Lookup with CRSIDs are returned in the parsed results
        The code is shared, so just exercise the inst query

        """

        def ibis_call_mock(method, args):
            return [
                {
                    "visible_name": "Joe Bloggs",
                    "identifiers": [{"scheme": "uuid", "value": "xxxxx-99999-123"}],
                    "attributes": [{"scheme": "firstName", "value": "Joe"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)
        (parsed_result, _) = client.get_people_info_for_query(
            {"id": "devops", "by": "lookup_institution"}
        )

        self.assertEqual(parsed_result, {})


class TestPeopleClientQueryByIdentifiers(TestCase):
    def test_querying_by_ids_passes_through_with_extra_fields(self):
        """
        Test that queries by id (other than crsid) get passed back out with the extra fields
        provided

        """
        people_client = PeopleClient()
        id_names_to_query_by = {name for name in identifier_names if name != "crsid"}

        for id_name in id_names_to_query_by:
            (result, id_scheme) = people_client.get_people_info_for_query(
                {"by": id_name, "id": "test-id", "extra_fields_for_results": {"a": "b", "c": 1}}
            )

            expected_scheme = identifier_names_to_schemes[id_name]

            self.assertEqual(id_scheme, expected_scheme)
            self.assertEqual(result, {f"test-id@{expected_scheme}": {"a": "b", "c": 1}})

    def test_querying_by_id_supports_multiple_ids(self):
        """
        Test that query by id supports multiple ids.
        The code for this is shared, so we just use a single id type

        """
        people_client = PeopleClient()
        (result, id_scheme) = people_client.get_people_info_for_query(
            {
                "by": "barcode",
                "ids": ["VV889", "VV999"],
                "extra_fields_for_results": {
                    "an_extra_field": "an_extra_item",
                },
            }
        )

        self.assertEqual(id_scheme, str(IdentifierSchemes.BARCODE))
        self.assertEqual(
            result,
            {
                f"vv889@{IdentifierSchemes.BARCODE}": {"an_extra_field": "an_extra_item"},
                f"vv999@{IdentifierSchemes.BARCODE}": {"an_extra_field": "an_extra_item"},
            },
        )

    def test_querying_by_id_supports_no_extra_fields(self):
        """
        Test that query by id supports no extra fields being passed in.
        The code for this is shared, so we just use a single id type

        """
        people_client = PeopleClient()
        (result, id_scheme) = people_client.get_people_info_for_query(
            {"by": "usn", "ids": ["300001", "300002"]}
        )

        self.assertEqual(id_scheme, str(IdentifierSchemes.USN))
        self.assertEqual(
            result, {f"300001@{IdentifierSchemes.USN}": {}, f"300002@{IdentifierSchemes.USN}": {}}
        )

    def test_lookup_can_be_queried_by_lql(self):
        """
        Test that Lookup can be queried by lql and the result parsed

        """

        def ibis_call_mock(method, args, fetch, offset, limit):
            self.assertEqual(method, "person_search")
            self.assertEqual(args, ('person: crsid = "wgd23"',))
            self.assertEqual(fetch, "visibleName,surname,firstName,all_identifiers")
            self.assertEqual(limit, PeopleClient.lql_query_page_size)
            self.assertEqual(offset, 0)

            return [
                {
                    "visible_name": "Monty Dawson",
                    "identifiers": [{"scheme": "crsid", "value": "wgd23"}],
                    "attributes": [{"scheme": "firstName", "value": "Monty"}],
                }
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)

        (parsed_result, scheme) = client.get_people_info_for_query(
            {"lql_query": 'person: crsid = "wgd23"', "by": "lql"}
        )

        self.assertEqual(scheme, CRSID_SCHEME)
        self.assertEqual(
            parsed_result,
            {
                f"wgd23@{CRSID_SCHEME}": {
                    "visible_name": "Monty Dawson",
                    "surname": None,
                    "forenames": "Monty",
                }
            },
        )

    def test_lql_query_follows_pages(self):
        """
        Test that the person client handles paginated lql queries, correctly crawling
        pages until no results are returned from Lookup.

        """

        num_people_to_return = int(PeopleClient.lql_query_page_size * 3.5)
        ibis_calls = 0

        def ibis_call_mock(method, args, fetch, offset, limit):
            nonlocal num_people_to_return
            nonlocal ibis_calls

            self.assertEqual(method, "person_search")
            self.assertEqual(args, ("person:in inst (UIS)",))
            self.assertEqual(fetch, "visibleName,surname,firstName,all_identifiers")
            self.assertEqual(limit, 500)
            self.assertEqual(offset, ibis_calls * PeopleClient.lql_query_page_size)

            results_start = ibis_calls * PeopleClient.lql_query_page_size
            results_stop = min(
                results_start + PeopleClient.lql_query_page_size, num_people_to_return
            )
            ibis_calls = ibis_calls + 1
            return [
                {
                    "visible_name": f"Person {index}",
                    "identifiers": [{"scheme": "crsid", "value": f"aa{index}"}],
                    "attributes": [{"scheme": "firstName", "value": "Monty"}],
                }
                for index in range(results_start, results_stop)
            ]

        client = create_people_client_with_ibis_mocked(ibis_call_mock)

        (parsed_result, _) = client.get_people_info_for_query(
            {"lql_query": "in inst (UIS)", "by": "lql"}
        )

        self.assertEqual(
            parsed_result,
            {
                f"aa{index}@{CRSID_SCHEME}": {
                    "visible_name": f"Person {index}",
                    "forenames": "Monty",
                    "surname": None,
                }
                for index in range(num_people_to_return)
            },
        )

    def test_lql_query_appends_person_modifier_to_search(self):
        """
        Test that 'person: ' is appended to the search if no provided

        """

        def ibis_call_mock(method, args, fetch, offset, limit):
            self.assertEqual(method, "person_search")
            self.assertEqual(args, ('person:crsid = "wgd23"',))
            self.assertEqual(fetch, "visibleName,surname,firstName,all_identifiers")
            self.assertEqual(limit, PeopleClient.lql_query_page_size)
            self.assertEqual(offset, 0)
            return []

        client = create_people_client_with_ibis_mocked(ibis_call_mock)

        # don't check the result - we validate that the person: prefix is added in the
        # ibis call mock
        client.get_people_info_for_query({"lql_query": 'crsid = "wgd23"', "by": "lql"})

    def test_fetch_by_org_id(self):
        """
        Test the people client fetches people by org_id

        """

        client = PeopleClient()
        client.legacy_card_client = MockedLegacyCardholderClient()

        (parsed_result, scheme) = client.get_people_info_for_query(
            {"ids": [23], "by": "legacy_carddb_organisation_id"}
        )

        self.assertEqual(scheme, str(IdentifierSchemes.LEGACY_CARDHOLDER))
        self.assertEqual(
            parsed_result,
            {f"jd1000u@{IdentifierSchemes.LEGACY_CARDHOLDER}": {"visible_name": "John Doe"}},
        )  # A single user 'jd1000u' is explicitly set and returned by TestLegacyCardClient.

    def test_fetch_by_university_student_institution(self):
        """
        Test the university student client fetch by institution.

        """
        mocked_student_client = mock.create_autospec(UniversityStudentClient)
        mocked_student_client.get_students_by_affiliation.return_value = [
            {
                "usn": "123",
                "visible_name": "Mr Jim Jimothy",
                "forenames": "Jim",
                "surname": "Jimothy",
                "affiliation_status": "PGRD",
            },
            {
                "usn": "142",
                "visible_name": "Professor Mary Maryland",
                "forenames": "Mary",
                "surname": "Maryland",
                "affiliation_status": "UGRD",
            },
        ]

        client = PeopleClient()
        client.university_student_client = mocked_student_client

        client = PeopleClient()
        client.university_student_client = mocked_student_client

        (parsed_result, scheme) = client.get_people_info_for_query(
            {"ids": ["HH"], "by": "student_institution"}
        )

        self.assertEqual(scheme, str(IdentifierSchemes.USN))
        self.assertEqual(
            parsed_result,
            {
                f"123@{IdentifierSchemes.USN}": {
                    "visible_name": "Mr Jim Jimothy",
                    "forenames": "Jim",
                    "surname": "Jimothy",
                    "affiliation_status": "PGRD",
                },
                f"142@{IdentifierSchemes.USN}": {
                    "visible_name": "Professor Mary Maryland",
                    "forenames": "Mary",
                    "surname": "Maryland",
                    "affiliation_status": "UGRD",
                },
            },
        )

        mocked_student_client.get_students_by_affiliation.assert_called_once_with(
            Identifier("HH", IdentifierSchemes.STUDENT_INSTITUTION), "students"
        )

    def test_fetch_by_university_student_maps_to_correct_affiliation(self):
        """
        Test that the `by` is correctly mapped to a query passed into the University
        Student Client.

        """
        mocked_student_client = mock.create_autospec(UniversityStudentClient)
        # mock four empty responses
        mocked_student_client.get_students_by_affiliation.side_effect = [[], [], [], []]

        client = PeopleClient()
        client.university_student_client = mocked_student_client

        client.get_people_info_for_query({"ids": ["AB"], "by": "student_institution"})
        mocked_student_client.get_students_by_affiliation.assert_called_with(
            Identifier("AB", IdentifierSchemes.STUDENT_INSTITUTION), "students"
        )

        client.get_people_info_for_query({"ids": ["AB123"], "by": "student_academic_plan"})
        mocked_student_client.get_students_by_affiliation.assert_called_with(
            Identifier("AB123", IdentifierSchemes.STUDENT_ACADEMIC_PLAN), "students"
        )

        client.get_people_info_for_query({"ids": ["CHR"], "by": "recent_graduate_institution"})
        mocked_student_client.get_students_by_affiliation.assert_called_with(
            Identifier("CHR", IdentifierSchemes.STUDENT_INSTITUTION), "recent-graduates"
        )

        client.get_people_info_for_query({"ids": ["AP2"], "by": "recent_graduate_academic_plan"})
        mocked_student_client.get_students_by_affiliation.assert_called_with(
            Identifier("AP2", IdentifierSchemes.STUDENT_ACADEMIC_PLAN), "recent-graduates"
        )

    def test_can_filter_by_affiliation_status(self):
        """
        Test that the 'affiliation_status' filter works.

        """
        mocked_student_client = mock.create_autospec(UniversityStudentClient)
        mocked_student_client.get_students_by_affiliation.return_value = [
            {
                "usn": "100",
                "visible_name": "Mr Jim Jimothy",
                "forenames": "Jim",
                "surname": "Jimothy",
                "affiliation_status": "AWRD",
            },
            {
                "usn": "200",
                "visible_name": "Professor Mary Maryland",
                "forenames": "Mary",
                "surname": "Maryland",
                "affiliation_status": "UGRD",
            },
            {
                "usn": "300",
                "visible_name": "Professor X Daw",
                "forenames": "X",
                "surname": "Daw",
                "affiliation_status": "PGRD",
            },
        ]

        client = PeopleClient()
        client.university_student_client = mocked_student_client

        pg_result, _ = client.get_people_info_for_query(
            {"ids": ["AB"], "by": "student_institution", "affiliation_status": "PGRD"}
        )
        self.assertEqual(
            pg_result,
            {
                f"300@{IdentifierSchemes.USN}": {
                    "visible_name": "Professor X Daw",
                    "forenames": "X",
                    "surname": "Daw",
                    "affiliation_status": "PGRD",
                }
            },
        )

        ug_result, _ = client.get_people_info_for_query(
            {"ids": ["AB"], "by": "student_institution", "affiliation_status": "UGRD"}
        )
        self.assertEqual(
            ug_result,
            {
                f"200@{IdentifierSchemes.USN}": {
                    "visible_name": "Professor Mary Maryland",
                    "forenames": "Mary",
                    "surname": "Maryland",
                    "affiliation_status": "UGRD",
                }
            },
        )

        no_match_result, _ = client.get_people_info_for_query(
            {"ids": ["AB"], "by": "student_institution", "affiliation_status": "OTHR"}
        )
        self.assertEqual(no_match_result, {})

    def test_fetch_by_university_hr_institution(self):
        """
        Test the university HR client fetch by institution

        """
        mocked_hr_client = mock.create_autospec(UniversityHRClient)
        mocked_hr_client.get_by_institution.return_value = [
            {
                "staff_number": "123",
                "visible_name": "Mr James Doe",
                "forenames": "James",
                "surname": "Doe",
            },
            {
                "staff_number": "4125",
                "visible_name": "Professor Jane Janeson",
                "forenames": "Jane",
                "surname": "Janeson",
            },
        ]

        client = PeopleClient()
        client.university_hr_client = mocked_hr_client

        (parsed_result, scheme) = client.get_people_info_for_query(
            {"ids": ["Q"], "by": "university_hr_institution"}
        )

        self.assertEqual(scheme, str(IdentifierSchemes.STAFF_NUMBER))
        self.assertEqual(
            parsed_result,
            {
                f"123@{IdentifierSchemes.STAFF_NUMBER}": {
                    "visible_name": "Mr James Doe",
                    "forenames": "James",
                    "surname": "Doe",
                },
                f"4125@{IdentifierSchemes.STAFF_NUMBER}": {
                    "visible_name": "Professor Jane Janeson",
                    "forenames": "Jane",
                    "surname": "Janeson",
                },
            },
        )

        mocked_hr_client.get_by_institution.assert_called_with("Q")
