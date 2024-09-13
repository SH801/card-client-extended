from typing import Callable, List, Mapping, Optional

from ibisclient import IbisAttribute, IbisIdentifier, IbisPerson

from ..card_client import LegacyCardholderClient
from ..people_client import PeopleClient


class MockedLegacyCardholderClient(LegacyCardholderClient):
    """
    Mock the LegacyCardClient to return a single legacy cardholder for any
    org_id provided

    """

    base_url = "https://test.com/legacycardholders"

    def __init__(self, config: Optional[Mapping] = {}):
        super(MockedLegacyCardholderClient, self).__init__(config)

    def get_people_by_legacy_org_id(*args, **kwargs):
        return [{"cam_uid": "jd1000u", "display_name": "John Doe"}]


def coerce_to_ibis_people(people: List[Mapping]) -> List[IbisPerson]:
    """
    A method to coerce a list of dicts representing mock Ibis people to a list
    of IbisPerson objects, only adding the attributes used within PeopleClient
    (visibleName and identifiers)

    """
    mocked_people: List[IbisPerson] = []

    for person in people:
        ibis_person = IbisPerson()
        ibis_person.visibleName = person["visible_name"]
        ibis_person.identifiers = []
        ibis_person.attributes = []

        for identifier in person["identifiers"]:
            ibis_identifier = IbisIdentifier()
            ibis_identifier.scheme = identifier["scheme"]
            ibis_identifier.value = identifier["value"]

            ibis_person.identifiers.append(ibis_identifier)

        for attribute in person["attributes"]:
            ibis_attribute = IbisAttribute()
            ibis_attribute.scheme = attribute["scheme"]
            ibis_attribute.value = attribute["value"]

            ibis_person.attributes.append(ibis_attribute)

        mocked_people.append(ibis_person)

    return mocked_people


def create_people_client_with_ibis_mocked(ibis_method_handler: Optional[Callable] = None):
    """
    A method that returns a PeopleClient with all Ibis methods mocked.
    An optional handler can be provided which will be called whenever
    an Ibis method would have been called by PeopleClient.

    """

    client = PeopleClient()

    def handle_group_get_members_call(*args, **kwargs):
        if ibis_method_handler:
            return coerce_to_ibis_people(
                ibis_method_handler("group_get_members", args, **kwargs) or []
            )
        return []

    def handle_institution_get_members_call(*args, **kwargs):
        if ibis_method_handler:
            return coerce_to_ibis_people(
                ibis_method_handler("inst_get_members", args, **kwargs) or []
            )
        return []

    def handle_person_list_call(*args, **kwargs):
        if ibis_method_handler:
            return coerce_to_ibis_people(
                ibis_method_handler("person_list_people", args, **kwargs) or []
            )
        return []

    def handle_person_search_call(*args, **kwargs):
        if ibis_method_handler:
            return coerce_to_ibis_people(
                ibis_method_handler("person_search", args, **kwargs) or []
            )
        return []

    client.group_methods.getMembers = handle_group_get_members_call
    client.inst_methods.getMembers = handle_institution_get_members_call
    client.person_methods.listPeople = handle_person_list_call
    client.person_methods.search = handle_person_search_call

    return client
