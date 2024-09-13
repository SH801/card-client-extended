from typing import Mapping, Optional
from unittest import TestCase

import requests_mock
from identitylib.identifiers import Identifier, IdentifierSchemes

from ..student_client import UniversityStudentClient


class TestUniversityStudentClient(TestCase):
    base_url = "https://test.com/university-student"

    def make_client(self, config: Optional[Mapping] = {}):
        return UniversityStudentClient({"base_url": self.base_url, **config})

    @requests_mock.Mocker()
    def test_get_students_by_institution(self, mocker):
        """
        Test filtering for students by institution.

        """

        client = self.make_client()
        mocker.get(
            f"{client.base_url}/students?affiliation=HH@{IdentifierSchemes.STUDENT_INSTITUTION}",
            json={
                "next": None,
                "previous": None,
                "results": [
                    {
                        "identifiers": [
                            {"value": "302224779", "scheme": str(IdentifierSchemes.USN)}
                        ],
                        "namePrefixes": "Mr",
                        "surname": "Doe",
                        "forenames": "John",
                        "affiliations": [
                            {
                                "value": "HH",
                                "status": "PGRD",
                                "scheme": str(IdentifierSchemes.STUDENT_INSTITUTION),
                                "start": "2016-10-01",
                            },
                            {
                                "value": "DV",
                                "status": "UGRD",
                                "scheme": str(IdentifierSchemes.STUDENT_INSTITUTION),
                                "start": "2016-10-01",
                            },
                        ],
                    }
                ],
            },
        )

        response = client.get_students_by_affiliation(
            Identifier("HH", IdentifierSchemes.STUDENT_INSTITUTION), "students"
        )
        self.assertEqual(
            response,
            [
                {
                    "usn": "302224779",
                    "affiliation_status": "PGRD",
                    "visible_name": "Mr John Doe",
                    "forenames": "John",
                    "surname": "Doe",
                }
            ],
        )

    @requests_mock.Mocker()
    def test_get_recent_graduates_by_academic_plan(self, mocker):
        """
        Test filtering for recent graduates using academic plan.

        """
        client = self.make_client()

        affiliation = f"A2@{IdentifierSchemes.STUDENT_ACADEMIC_PLAN}"
        mocker.get(
            f"{client.base_url}/recent-graduates?affiliation={affiliation}",
            json={
                "next": None,
                "previous": None,
                "results": [
                    {
                        "identifiers": [
                            {"value": "1243123", "scheme": str(IdentifierSchemes.USN)}
                        ],
                        "namePrefixes": "Professor",
                        "surname": "Peterhouse",
                        "forenames": "Peter John",
                        "affiliations": [
                            {
                                "value": "A2",
                                "status": "UGRD",
                                "scheme": str(IdentifierSchemes.STUDENT_ACADEMIC_PLAN),
                                "start": "2016-10-01",
                                "end": "2021-12-19",
                            }
                        ],
                    }
                ],
            },
        )

        response = client.get_students_by_affiliation(
            Identifier("A2", IdentifierSchemes.STUDENT_ACADEMIC_PLAN), "recent-graduates"
        )
        self.assertEqual(
            response,
            [
                {
                    "usn": "1243123",
                    "affiliation_status": "UGRD",
                    "visible_name": "Professor Peter John Peterhouse",
                    "forenames": "Peter John",
                    "surname": "Peterhouse",
                }
            ],
        )

    @requests_mock.Mocker()
    def test_can_handle_empty_response(self, mocker):
        """
        Test that an empty response is handled correctly.

        """
        client = self.make_client()

        affiliation = f"BP23531@{IdentifierSchemes.STUDENT_ACADEMIC_PLAN}"
        mocker.get(
            f"{client.base_url}/students?affiliation={affiliation}",
            json={"next": None, "previous": None, "results": []},
        )

        response = client.get_students_by_affiliation(
            Identifier("BP23531", IdentifierSchemes.STUDENT_ACADEMIC_PLAN), "students"
        )
        self.assertEqual(response, [])
