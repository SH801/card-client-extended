from csv import DictReader, DictWriter
from datetime import datetime
from logging import getLogger
from typing import Dict, List, Mapping, Optional

from progress.spinner import PieSpinner

from .card_client import CardClient
from .consts import DEFAULT_FIELDS

LOG = getLogger(__name__)


def get_field_names(config: Mapping, card: Dict) -> List[str]:
    """
    Get the fields to export based either on the output fields passed in on config,
    or by combining our default fields with any of the keys of one of our card
    objects. We avoid using a set here to keep the ordering consistent.

    """
    export_fields = config.get("fields")

    if not export_fields:
        export_fields = DEFAULT_FIELDS.copy()
        for key in sorted(card.keys()):
            if key not in export_fields:
                export_fields.append(key)

    for required_field in ["id", "updatedAt"]:
        if required_field not in export_fields:
            export_fields.append(required_field)

    return export_fields


def export_issued_cards(
    configuration: Mapping,
    card_client: CardClient,
    *,
    silent: bool = False,
):
    """
    Allows all issued personal cards to be exported to a file specified within the
    configuration provided.

    """

    progress = PieSpinner() if not silent else None

    output_config = configuration.get("output", {})
    export_location = output_config.get("file", "export.csv")

    LOG.info(f"Writing all issued cards to {export_location}")
    with open(export_location, "w", newline="") as export_file:
        writer: Optional[DictWriter] = None

        for index, card in enumerate(
            card_client.all_cards(status="ISSUED", card_type="MIFARE_PERSONAL")
        ):
            normalized_card = CardClient.normalize_card(card)
            # Lazy-init the dict writer in order to allow us to set the field names
            # based on the fields that are returned from the Card API
            if not writer:
                field_names = get_field_names(output_config, normalized_card)
                # we need the updatedAt and id to be within the export in order to allow
                # incremental updates to this

                writer = DictWriter(export_file, fieldnames=field_names, extrasaction="ignore")
                writer.writeheader()

            if progress and index % 100 == 0:
                progress.message = f"   Fetching cards ({index}) "
                progress.update()

            writer.writerow(normalized_card)

        if progress:
            progress.finish()


def update_issued_cards_export(configuration: Mapping, card_client: CardClient):
    """
    Allows a previously generated export of cards to be updated in-place with an
    incremental query of the Card API to fetch any changes since the last export.

    Requires that all cards within the existing export have an 'id' and 'updatedAt'
    field, as the 'id' is used to determine which cards to remove if they are no
    longer issued, and the 'updatedAt' is used to find the most recently updated
    card in the export in order to fetch any changes occuring after this card
    was updated.

    """
    export_location = configuration.get("output", {}).get("file", "export.csv")

    latest_updated_at: Optional[datetime] = None
    # record the field names from the existing export so we can write the same fields
    # back when updating.
    field_names = []
    existing_cards = []

    with open(export_location, "r", newline="") as export_file:
        LOG.info(f"Updating cards in-place for file {export_location}")

        existing_data_reader = DictReader(export_file)
        field_names = existing_data_reader.fieldnames

        for card in existing_data_reader:
            if not card.get("updatedAt") or not card.get("id"):
                raise RuntimeError("Unable to update export file without updatedAt and id fields")

            existing_cards.append(card)

            updated_at_date = datetime.fromisoformat(card["updatedAt"].rstrip("Z"))
            if not latest_updated_at or updated_at_date > latest_updated_at:
                latest_updated_at = updated_at_date

    if not latest_updated_at:
        raise RuntimeError("Unable to determine last update point from export")

    LOG.info(f"Querying for cards updated since most recent card in export ({latest_updated_at})")

    ids_of_cards_to_remove = set()
    issued_cards_changed: Dict[str, Dict] = {}

    for updated_card in card_client.all_cards(
        updated_at__gte=latest_updated_at.isoformat(),
        card_type="MIFARE_PERSONAL",
    ):
        if updated_card.get("status") != "ISSUED":
            ids_of_cards_to_remove.add(updated_card["id"])
        else:
            issued_cards_changed[updated_card["id"]] = updated_card

    number_of_cards_removed = 0
    number_of_cards_updated = 0
    number_of_cards_added = 0

    with open(export_location, "w", newline="") as export_file:
        writer = DictWriter(export_file, fieldnames=field_names, extrasaction="ignore")
        writer.writeheader()

        for existing_card in existing_cards:
            if existing_card["id"] in ids_of_cards_to_remove:
                number_of_cards_removed += 1
                continue

            updated_card = issued_cards_changed.pop(existing_card["id"], None)
            if updated_card:
                number_of_cards_updated += 1
                writer.writerow(CardClient.normalize_card(updated_card))
            else:
                writer.writerow(existing_card)

        # we have removed any cards from issued_cards_changed which already exist in the
        # export, so any remaining in issued_cards_changed are new cards
        number_of_cards_added = len(issued_cards_changed)
        for new_card in issued_cards_changed.values():
            writer.writerow(CardClient.normalize_card(new_card))

    LOG.info(f"  {number_of_cards_added} newly issued cards have been added")
    LOG.info(f"  {number_of_cards_updated} issued cards have been updated in-place")
    LOG.info(f"  {number_of_cards_removed} cards have been un-issued and removed")
    LOG.info("Incremental update complete")
