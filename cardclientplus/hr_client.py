from logging import getLogger
from typing import Any, Dict, List, Mapping, Optional

from identitylib.identifiers import Identifier, IdentifierSchemes

from .api_client import IdentityAPIClient

LOG = getLogger(__name__)


class UniversityHRClient(IdentityAPIClient):
    """
    Class provides methods to query the University Human Resources API.

    """

    default_version = "v1alpha2"
    default_base_url = "https://api.apps.cam.ac.uk/university-human-resources"

    def __init__(self, config: Optional[Mapping] = {}):
        config = {**config, **config.get("university_human_resources_api", {})}

        version = config.get("api_version", self.default_version)
        self.base_url = f'{config.get("base_url", self.default_base_url).rstrip("/")}/{version}'

        super().__init__(config)

    def get_by_institution(self, inst_id: int) -> List[Dict[str, Any]]:
        """
        Query the HR API endpoint by affiliation and return the staff number,
        status, and name fields

        """
        inst_identifier = Identifier(inst_id, IdentifierSchemes.HR_INSTITUTION)
        staff_members = self._yield_paged_request(
            f"{self.base_url}/staff?affiliation={inst_identifier}",
            params={"page_size": self.page_size},
        )

        parsed_staff_members = []
        for member in staff_members:
            staff_number = next(
                (
                    id["value"]
                    for id in member["identifiers"]
                    if id["scheme"] == str(IdentifierSchemes.STAFF_NUMBER)
                )
            )
            status = next(
                (
                    affiliation["status"]
                    for affiliation in member["affiliations"]
                    if (
                        affiliation["value"] == inst_id
                        and affiliation["scheme"] == str(IdentifierSchemes.HR_INSTITUTION)
                        and
                        # filter out people who are just `members`, as they were excluded
                        # from existing exports from the card system
                        affiliation["status"] != "Member"
                    )
                ),
                None,
            )

            if not status:
                continue

            parsed_staff_members.append(
                {
                    "staff_number": staff_number,
                    "visible_name": (
                        f"{member['namePrefixes']} {member['forenames']} {member['surname']}"
                    ),
                    "forenames": member["forenames"],
                    "surname": member["surname"],
                }
            )

        return parsed_staff_members
