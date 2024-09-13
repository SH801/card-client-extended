from logging import getLogger
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .api_client import IdentityAPIClient
from .identifiers import id_to_str, identifier_schemes_to_names
from .utils import chunks

LOG = getLogger(__name__)


class CardClient(IdentityAPIClient):
    """
    A client providing methods to efficiently query the Card API

    """

    default_version = "v1beta1"
    default_base_url = "https://api.apps.cam.ac.uk/card"

    def __init__(self, config: Optional[Mapping] = {}):
        config = {**config, **config.get("card_api", {})}

        version = config.get("api_version", self.default_version)
        self.base_url = f'{config.get("base_url", self.default_base_url).rstrip("/")}/{version}'

        super(CardClient, self).__init__(config)

    @staticmethod
    def normalize_card(card: Mapping) -> Mapping:
        """
        Normalizes a card DTO from the Card API into a flat structure containing all
        identifiers as top-level fields, named using the mapping above.

        """
        identifiers = card["identifiers"]

        name_parsed_identifiers = {
            name: next((id["value"] for id in identifiers if id["scheme"] == scheme), "").lower()
            for (scheme, name) in identifier_schemes_to_names.items()
        }

        name_parsed_identifiers["mifare_id_hex"] = (
            format(int(name_parsed_identifiers["mifare_id"]), "x").zfill(8)
            if name_parsed_identifiers["mifare_id"].isnumeric()
            else ""
        )

        return {
            **name_parsed_identifiers,
            # exclude the original identifiers array
            **{key: value for key, value in card.items() if key != "identifiers"},
        }

    @staticmethod
    def get_identifier_by_scheme(card: Mapping, scheme: str) -> Optional[str]:
        """
        Finds an identifier on the given card by the identifier scheme provided.
        Returns the identifier in full string form, i.e. `<value>@<scheme>`

        """
        return next(
            (
                id_to_str(id["value"], id["scheme"])
                for id in card["identifiers"]
                if id["scheme"] == scheme
            ),
            None,
        )

    def cards_for_identifiers(
        self,
        identifiers: Iterable[str],
        *,
        chunk_size: Optional[int] = 50,
        params: Optional[Dict[str, Any]] = {},
    ) -> Iterable[Mapping]:
        """
        Queries the Card API for the given list of identifiers. The query is made
        in batches in order to reduce load and therefore this method returns an
        iterator which will emit results as they are received.

        """

        for chunk in chunks(list(identifiers), chunk_size):
            yield from self._yield_paged_request(
                f"{self.base_url}/cards/filter/",
                self.r.post,
                json={"identifiers": chunk},
                params={"page_size": self.page_size, **params},
            )

    def all_cards(self, **params) -> Iterable[Mapping]:
        """
        Queries the Card API for all cards, using the given params. Returns an iterator
        which will emit results as each page of cards is received.

        """
        return self._yield_paged_request(
            f"{self.base_url}/cards/", params={"page_size": self.page_size, **params}
        )

    def get_card_detail(self, card_uuid: str) -> Mapping:
        """
        Queries for the detail of a single card by UUID

        """
        request = self._request_with_retry(f"{self.base_url}/cards/{card_uuid}/")
        request.raise_for_status()
        return request.json()


class LegacyCardholderClient(IdentityAPIClient):
    """
    Class provides methods to query the Legacy Cardholder API

    """

    default_base_url = "https://api.apps.cam.ac.uk/legacycardholders"

    def __init__(self, config: Optional[Mapping] = {}):
        config = {**config, **config.get("legacy_cardholder_api", {})}

        self.base_url = f'{config.get("base_url", self.default_base_url).rstrip("/")}'
        super(LegacyCardholderClient, self).__init__(config)

    def get_people_by_legacy_org_id(self, ids: List[int]) -> List[str]:
        """
        Fetch cardholders from the Legacy Cardholder API and filter results by
        legacy card organisation db identifier.
        """

        LOG.info(f"Fetching members by org_id {ids}")

        request = self._request_with_retry(f"{self.base_url}")
        request.raise_for_status()

        members = [
            {"cam_uid": k["cam_uid"], "display_name": k["display_name"]}
            for k in request.json()["records"]
            if any(x in k["org_id"] for x in ids)
        ]

        return members
