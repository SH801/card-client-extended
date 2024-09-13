from typing import Mapping, Optional
from unittest import TestCase

import requests_mock
from identitylib.identifiers import IdentifierSchemes

from ..hr_client import UniversityHRClient


class TestUniversityHRClient(TestCase):
    base_url = "https://test.com/university-human-resources"

    def make_client(self, config: Optional[Mapping] = {}):
        return UniversityHRClient({"base_url": self.base_url, **config})

    @requests_mock.Mocker()
    def test_get_by_by_institution(self, mocker, **kwargs):
        """
        Test request parsing from University HR API.

        """

        client = self.make_client()
        affiliation = f"CHR@{IdentifierSchemes.HR_INSTITUTION}"
        mocker.get(
            f"{client.base_url}/staff?affiliation={affiliation}",
            json={
                "next": None,
                "previous": None,
                "results": [
                    {
                        "identifiers": [
                            {"value": "124123", "scheme": str(IdentifierSchemes.STAFF_NUMBER)}
                        ],
                        "namePrefixes": "Mr",
                        "surname": "Doephenor",
                        "forenames": "James",
                        "affiliations": [
                            {
                                "value": "CHR",
                                "status": "Senior Developer",
                                "scheme": str(IdentifierSchemes.HR_INSTITUTION),
                                "start": "2016-10-01",
                                "end": None,
                            },
                        ],
                    }
                ],
            },
        )

        client = self.make_client()
        response = client.get_by_institution("CHR")
        self.assertEqual(
            response,
            [
                {
                    "staff_number": "124123",
                    "visible_name": "Mr James Doephenor",
                    "forenames": "James",
                    "surname": "Doephenor",
                }
            ],
        )

    @requests_mock.Mocker()
    def test_members_are_filtered_out(self, mocker, **kwargs):
        """
        Test members are filtered out

        """

        client = self.make_client()
        affiliation = f"HH@{IdentifierSchemes.HR_INSTITUTION}"
        mocker.get(
            f"{client.base_url}/staff?affiliation={affiliation}",
            json={
                "next": None,
                "previous": None,
                "results": [
                    {
                        "identifiers": [
                            {"value": "1578", "scheme": str(IdentifierSchemes.STAFF_NUMBER)}
                        ],
                        "namePrefixes": "Mr",
                        "surname": "Ha",
                        "forenames": "Jim",
                        "affiliations": [
                            {
                                "value": "HH",
                                "status": "Member",
                                "scheme": str(IdentifierSchemes.HR_INSTITUTION),
                                "start": "2002-10-01",
                                "end": None,
                            },
                        ],
                    }
                ],
            },
        )

        client = self.make_client()
        response = client.get_by_institution("HH")

        self.assertEqual(response, [])

    @requests_mock.Mocker()
    def test_members_with_additional_affiliation_are_included(self, mocker, **kwargs):
        """
        Test members with an additional affiliation are included.

        """

        client = self.make_client()
        affiliation = f"ABC@{str(IdentifierSchemes.HR_INSTITUTION)}"
        mocker.get(
            f"{client.base_url}/staff?affiliation={affiliation}",
            json={
                "next": None,
                "previous": None,
                "results": [
                    {
                        "identifiers": [
                            {"value": "1534", "scheme": str(IdentifierSchemes.STAFF_NUMBER)}
                        ],
                        "namePrefixes": "Mr",
                        "surname": "Sam",
                        "forenames": "James",
                        "affiliations": [
                            {
                                "value": "ABC",
                                "status": "Member",
                                "scheme": str(IdentifierSchemes.HR_INSTITUTION),
                                "start": "2002-10-01",
                                "end": None,
                            },
                            {
                                "value": "ABC",
                                "status": "Senior Scientist",
                                "scheme": str(IdentifierSchemes.HR_INSTITUTION),
                                "start": "2002-10-01",
                                "end": None,
                            },
                        ],
                    }
                ],
            },
        )

        client = self.make_client()
        response = client.get_by_institution("ABC")

        self.assertEqual(
            response,
            [
                {
                    "staff_number": "1534",
                    "visible_name": "Mr James Sam",
                    "forenames": "James",
                    "surname": "Sam",
                }
            ],
        )
