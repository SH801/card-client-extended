"""
Card API Client

Usage:
    cardclientplus (-h | --help)
    cardclientplus export [--config=FILE]... [--quiet] [--debug]
    cardclientplus export-issued-cards [--incremental-update] [--config=FILE]... [--quiet] [--debug]
    cardclientplus card-detail <identifier> [--config=FILE]... [--identifier-scheme=SCHEME]
                                        [--normalize] [--quiet] [--debug]

Options:
    -h, --help                  Show a brief usage summary.

    -n, --normalize             Whether to normalize the output from card-detail.
    --identifier-scheme=SCHEME  The identifier scheme of the identifier provided to card-detail.
    -q, --quiet                 Reduce logging verbosity.
    -d --debug                  Log debugging information.


    -c, --config=FILE           Specify configuration file(s) to use [default: config.yml].
    -i, --incremental-update    Whether to update an export incrementally - only available when
                                exporting issued cards.
"""

import logging
from typing import List

from deepmerge import always_merger
from docopt import docopt

from .card_client import CardClient
from .export import export_cards, print_card_detail
from .export_issued_cards import export_issued_cards, update_issued_cards_export
from .people_client import PeopleClient
from .utils import load_yaml_file

LOG = logging.getLogger(__name__)


def load_settings(paths: List[str]):
    settings = {}
    for path in paths:
        LOG.info("Loading settings from %s", path)
        settings = always_merger.merge(settings, load_yaml_file(path))
    return settings or {}


def main():
    opts = docopt(__doc__)

    logging.basicConfig(
        level=logging.DEBUG
        if opts["--debug"]
        else logging.WARN
        if opts["--quiet"]
        else logging.INFO
    )

    config = load_settings(opts["--config"])
    card_client = CardClient(config.get("environment") or {})
    people_client = PeopleClient(config.get("lookup_credentials"), config.get("environment") or {})

    if opts["export"]:
        export_cards(config, card_client, people_client, silent=opts["--quiet"])
    if opts["export-issued-cards"]:
        if opts["--incremental-update"]:
            update_issued_cards_export(config, card_client)
        else:
            export_issued_cards(config, card_client, silent=opts["--quiet"])
    if opts["card-detail"]:
        print_card_detail(
            card_client, opts["<identifier>"], opts["--identifier-scheme"], opts["--normalize"]
        )
