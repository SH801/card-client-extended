import logging
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from ibisclient import GroupMethods, IbisPerson, InstitutionMethods, createConnection
from ibisclient.methods import PersonMethods
from identitylib.identifiers import Identifier, IdentifierSchemes

from .card_client import LegacyCardholderClient
from .hr_client import UniversityHRClient
from .identifiers import (
    CRSID_SCHEME,
    id_to_str,
    identifier_names,
    identifier_names_to_schemes,
)
from .student_client import UniversityStudentClient
from .utils import chunks

LOG = logging.getLogger(__name__)


class PeopleClient:
    """
    Class which provides methods to query external systems (at the moment
    only Lookup) in order to retrieve personal information about
    cardholders based on different forms of identifiers or query methods.

    """

    """
    The page size to request when making a query to Lookup via LQL

    """
    lql_query_page_size = 500
    fetch_fields = "visibleName,surname,firstName,all_identifiers"

    def __init__(
        self,
        lookup_config: Optional[Mapping] = None,
        environment_config: Optional[Mapping] = {},
    ):
        # Eagerly init the lookup client and associated methods
        self.ibis_connection = createConnection()

        if lookup_config and lookup_config.get("username") and lookup_config.get("password"):
            self.ibis_connection.set_username(lookup_config["username"])
            self.ibis_connection.set_password(lookup_config["password"])

        self.inst_methods = InstitutionMethods(self.ibis_connection)
        self.group_methods = GroupMethods(self.ibis_connection)
        self.person_methods = PersonMethods(self.ibis_connection)

        # The keys in this dict relate to the 'by' field added to a query in the configuration
        # provided by a user, providing a method for fetching personal information by a given
        # set of ids within the query and joining that with any 'extra_fields_for_results'
        # provided in the query
        self.query_by_to_fetch_method: Dict[str, Callable] = {
            **{
                identifier_name: self._map_identifiers_to_extra_fields
                for identifier_name in identifier_names
            },
            "lookup_institution": self._fetch_lookup_members,
            "lookup_group": self._fetch_lookup_members,
            "lql": self._fetch_by_lql,
            # crsid is a special case where we can fetch members from lookup
            "crsid": self._fetch_lookup_members_by_crsid,
            "legacy_carddb_organisation_id": self._fetch_by_org_id,
            "student_institution": self._fetch_by_university_student_affiliation,
            "student_academic_plan": self._fetch_by_university_student_affiliation,
            "recent_graduate_institution": self._fetch_by_university_student_affiliation,
            "recent_graduate_academic_plan": self._fetch_by_university_student_affiliation,
            "university_hr_institution": self._fetch_by_university_hr_institution,
        }

        self.legacy_card_client = LegacyCardholderClient(environment_config)
        self.university_student_client = UniversityStudentClient(environment_config)
        self.university_hr_client = UniversityHRClient(environment_config)

    def get_people_info_for_query(self, query: Mapping) -> Tuple[Dict[str, Mapping], str]:
        """
        Handles validation of a query as specified within the configuration
        and passes off to one of the methods in `query_by_to_fetch_method`
        to fetch personal information by the given ids.

        In the case of a query with a `by` that does not relate to Lookup
        no further personal information will be returned beyond what is
        provided in the `extra_fields_for_results` section of the query.

        Returns:
        (0) a dictionary keyed by identifier where each item is a dict
        containing any personal information that can be fetched using the
        given `by` and `ids` joined with any `extra_fields_for_results`
        provided.
        (1) the identifier scheme that the results relate to

        """
        by = query.get("by")
        if by not in self.query_by_to_fetch_method.keys():
            raise ValueError(
                f"Invalid `by` field on query, available options are "
                f"{list(self.query_by_to_fetch_method.keys())}"
            )

        ids = query.get("ids", [query.get("id")] if query.get("id") else None)
        lql_query = query.get("lql_query", None)
        extra_fields = query.get("extra_fields_for_results") or {}
        affiliation_status = query.get("affiliation_status")

        if by == "lql":
            if not lql_query or not isinstance(lql_query, str):
                raise ValueError("Query by lql must contain a string `lql_query` attribute")
            return self.query_by_to_fetch_method[by](lql_query, by, extra_fields)

        elif not isinstance(ids, list) or len(ids) == 0:
            raise ValueError(f"Query does not contain an id or list of ids: {query}")

        return self.query_by_to_fetch_method[by](ids, by, extra_fields, affiliation_status)

    def _fetch_by_org_id(
        self, ids: List[int], by: str, extra_fields: Mapping, *args
    ) -> Tuple[Dict[str, Mapping], str]:
        """
        Fetches members from the Legacy Cardholder API and filters the returned
        results based on the legacy cardholder organisation db id
        """

        legacy_cardholders = self.legacy_card_client.get_people_by_legacy_org_id(ids)

        id_scheme = identifier_names_to_schemes["legacy_card_holder_id"]

        ids_to_extra_fields = {}
        for id in legacy_cardholders:
            ids_to_extra_fields[id_to_str(id["cam_uid"], id_scheme)] = {
                "visible_name": id["display_name"],
                **extra_fields,
            }

        return (ids_to_extra_fields, id_scheme)

    def _fetch_by_university_student_affiliation(
        self, ids: List[int], by: str, extra_fields: Mapping, affiliation_status: Optional[str]
    ) -> Tuple[Dict[str, Mapping], str]:
        """
        Fetch students from the University Student API, mapping the `by` provided to a
        query in the university student API. Allows filtering student and recent graduates
        by either institution or academic plan.

        """
        LOG.info(f"Filtering by {by} for ids {ids}")

        id_scheme = identifier_names_to_schemes["usn"]
        by_to_student_type_and_affiliation_scheme = {
            "student_institution": ("students", IdentifierSchemes.STUDENT_INSTITUTION),
            "student_academic_plan": ("students", IdentifierSchemes.STUDENT_ACADEMIC_PLAN),
            "recent_graduate_institution": (
                "recent-graduates",
                IdentifierSchemes.STUDENT_INSTITUTION,
            ),
            "recent_graduate_academic_plan": (
                "recent-graduates",
                IdentifierSchemes.STUDENT_ACADEMIC_PLAN,
            ),
        }
        (student_type, affiliation_scheme) = by_to_student_type_and_affiliation_scheme[by]

        ids_to_extra_fields = {}
        for affiliation_value in ids:
            affiliation_identifier = Identifier(affiliation_value, affiliation_scheme)
            students_iterator = self.university_student_client.get_students_by_affiliation(
                affiliation_identifier, student_type
            )
            for student in students_iterator:
                # filter out students without the required affiliation status
                # if an affiliation status is provided
                if affiliation_status and student["affiliation_status"] != affiliation_status:
                    continue

                ids_to_extra_fields[id_to_str(student["usn"], id_scheme)] = {
                    "visible_name": student["visible_name"],
                    "forenames": student["forenames"],
                    "surname": student["surname"],
                    "affiliation_status": student["affiliation_status"],
                    **extra_fields,
                }

        return (ids_to_extra_fields, id_scheme)

    def _fetch_by_university_hr_institution(
        self, ids: List[int], by: str, extra_fields: Mapping, *args
    ):
        """
        Fetches staff members from the University HR API for the institutions
        provided within ids. Return a dictionary keyed by long-form staff_number
        identifier, to the fields for this staff member.

        """
        LOG.info(f"Filtering by {by} for ids {ids}")

        id_scheme = identifier_names_to_schemes["staff_number"]

        staff_members = {}
        for inst_identifier in ids:
            for member in self.university_hr_client.get_by_institution(inst_identifier):
                staff_members[id_to_str(member["staff_number"], id_scheme)] = {
                    "visible_name": member["visible_name"],
                    "forenames": member["forenames"],
                    "surname": member["surname"],
                    **extra_fields,
                }

        return (staff_members, id_scheme)

    def _fetch_lookup_members(
        self, ids: List[str], by: str, extra_fields: Mapping, *args
    ) -> Tuple[Dict[str, Mapping], str]:
        """
        Fetches members from Lookup by querying either an institution or group
        by the given id provided. Returns a dict keyed by crsid with each item
        being a dict containing the visible name of the person from Lookup
        under the key `name` and any further fields provided in `extra_fields`.

        """
        crsid_to_fields: Dict[str, Mapping] = {}

        # we know that by will either be lookup_institution or lookup_group as
        # this method should only be called from get_people_info_for_query
        fetch_method = (
            self.inst_methods.getMembers
            if by == "lookup_institution"
            else self.group_methods.getMembers
        )

        for id in ids:
            LOG.info(f"Fetching members of {by} {id}")

            members = fetch_method(id, self.fetch_fields)
            crsid_to_fields.update(self._map_crsid_to_fields(members, extra_fields))

        return (crsid_to_fields, CRSID_SCHEME)

    def _fetch_by_lql(self, lql_query: str, by: str, extra_fields: Mapping, *args):
        """
        Fetches members from Lookup using the given lql query. Returns a dict
        keyed by crsid with each item being a dict containing the visible name
        of the person from Lookup under the key `visible_name` and any further fields
        provided in `extra_fields`.

        """
        lql_query = f"person:{lql_query}" if not lql_query.startswith("person:") else lql_query
        LOG.info(f"Fetching people using {lql_query}")

        members = self._get_lookup_members_by_lql(lql_query)
        crsid_to_fields = self._map_crsid_to_fields(members, extra_fields)
        return (crsid_to_fields, CRSID_SCHEME)

    def _get_lookup_members_by_lql(self, query: str, offset: int = 0):
        """
        Fetches all members by lql query - recursively following pages of results using
        the offset param until a response is returned that is smaller than the page size
        requested, returning all results from the paged requests in a single list.

        """
        LOG.debug(f"Quering via lql with query {query} and offset {offset}")
        members = self.person_methods.search(
            query, offset=offset, limit=self.lql_query_page_size, fetch=self.fetch_fields
        )
        if len(members) < self.lql_query_page_size:
            return members
        return members + self._get_lookup_members_by_lql(query, offset + len(members))

    def _fetch_lookup_members_by_crsid(
        self, ids: List[str], by: str, extra_fields: Mapping, *args
    ) -> Dict[str, Mapping]:
        """
        Acts in the same way as `_fetch_lookup_members`, but queries Lookup
        using crsids. Chunks requests by crsid as suggested by Ibis client
        docs: (https://www.lookup.cam.ac.uk/doc/ws-pydocs3/ibisclient.methods.PersonMethods.html)

        """
        crsid_to_fields: Dict[str, Mapping] = {}
        LOG.info(f"Fetching members by {len(ids)} crsid(s)")

        for chunked_crsids in chunks(ids, 100):
            members = self.person_methods.listPeople(",".join(chunked_crsids), self.fetch_fields)
            crsid_to_fields.update(self._map_crsid_to_fields(members, extra_fields))

        return (crsid_to_fields, CRSID_SCHEME)

    def _map_identifiers_to_extra_fields(
        self, ids: List[str], by: str, extra_fields: Mapping, *args
    ) -> Dict[str, Mapping]:
        """
        This method handles the case that we are querying by an id that
        Lookup doesn't know about. In which case we simply return a dict
        keyed by the identifier provided, with each item being the
        `extra_fields` passed in.

        """

        LOG.info(f"Returning people for {len(ids)} identifiers of type {by}")

        id_scheme = identifier_names_to_schemes[by]
        ids_to_extra_fields = {id_to_str(id, id_scheme): extra_fields for id in ids}
        return (ids_to_extra_fields, id_scheme)

    def _map_crsid_to_fields(
        self, ibis_people: List[IbisPerson], extra_fields: Mapping
    ) -> Dict[str, str]:
        """
        Takes a list of ibis people and extra fields and produces a dict keyed by crsid
        with each item being a dict containing the visible name of the person and any
        extra fields passed in.

        """

        crsid_to_fields = {}

        for member in ibis_people:
            first_name = next(
                (attr.value for attr in member.attributes if attr.scheme == "firstName"), None
            )
            crsid = next((id.value for id in member.identifiers if id.scheme == "crsid"), None)
            if crsid:
                crsid_to_fields[id_to_str(crsid, CRSID_SCHEME)] = {
                    "visible_name": member.visibleName,
                    "surname": member.surname,
                    "forenames": first_name,
                    **extra_fields,
                }

        return crsid_to_fields
