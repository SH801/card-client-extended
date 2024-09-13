from logging import getLogger
from typing import Any, Dict, List, Mapping, Optional

from identitylib.identifiers import Identifier, IdentifierSchemes

from .api_client import IdentityAPIClient

LOG = getLogger(__name__)


class UniversityStudentClient(IdentityAPIClient):
    """
    Class provides methods to query the University Student API.

    """

    default_version = "v1alpha2"
    default_base_url = "https://api.apps.cam.ac.uk/university-student"

    def __init__(self, config: Optional[Mapping] = {}):
        config = {**config, **config.get("university_student_api", {})}

        version = config.get("api_version", self.default_version)
        self.base_url = f'{config.get("base_url", self.default_base_url).rstrip("/")}/{version}'

        super(UniversityStudentClient, self).__init__(config)

    def get_students_by_affiliation(
        self, affiliation_id: Identifier, student_type: str = "students"
    ) -> List[Dict]:
        """
        Query the Student API endpoint and filter by affiliation.

        """
        students_iterator = self._yield_paged_request(
            f"{self.base_url}/{student_type}?affiliation={affiliation_id}"
        )

        return list(
            map(
                lambda student: self._normalize_student(student, affiliation_id), students_iterator
            )
        )

    def _normalize_student(
        self,
        student: str,
        affiliation_id: Identifier,
    ) -> Dict[str, Any]:
        """
        Returns a normalized students from the 'full' student entity returned from the
        University HR API, uses the affiliation details passed in to pick out the status
        for the relevant affiliation on the student entity.

        """
        usn = next(
            (
                id["value"]
                for id in student["identifiers"]
                if id["scheme"] == str(IdentifierSchemes.USN)
            )
        )

        affiliation_status = next(
            (
                affiliation["status"]
                for affiliation in student["affiliations"]
                if (
                    affiliation["value"] == affiliation_id.value
                    and affiliation["scheme"] == str(affiliation_id.scheme)
                )
            )
        )

        visible_name = f"{student['namePrefixes']} {student['forenames']} {student['surname']}"
        return {
            "usn": usn,
            "affiliation_status": affiliation_status,
            "visible_name": visible_name,
            "forenames": student["forenames"],
            "surname": student["surname"],
        }
