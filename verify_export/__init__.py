"""
Usage:
    verify_export (-h | --help)
    verify_export <expected> <actual>

Options:
    -h, --help           Show a brief usage summary.
"""

import csv
from collections import namedtuple
from csv import DictReader
from typing import List

from docopt import docopt

Difference = namedtuple(
    "Difference", ["mifare_id", "crsid", "missing", "grade_diff", "crsid_diff"]
)


def main():
    options = docopt(__doc__)

    actual_by_mifare_id = {}
    differences: List[Difference] = []

    with open(options["<actual>"], "r") as actual_csv:
        for row in DictReader(actual_csv):
            actual_by_mifare_id[row["mifare_id"]] = row

    with open(options["<expected>"], "r") as expected_csv:
        for row in DictReader(expected_csv):
            mifare_id = row["Mifare ID decimal"]
            actual_row = actual_by_mifare_id.get(mifare_id)

            if not actual_row:
                differences.append(
                    Difference(mifare_id, row.get("CRSID", "").lower(), True, False, False)
                )
                continue

            grade_different = actual_row["grade"] != row["Grade"]
            crsid_different = actual_row["crsid"] != row.get("CRSID", "").lower()

            if grade_different or crsid_different:
                differences.append(
                    Difference(
                        mifare_id, actual_row["crsid"], False, grade_different, crsid_different
                    )
                )

    with open("differences.csv", "w") as differences_csv:
        writer = csv.writer(differences_csv)
        writer.writerow(("mifare_id", "crsid", "missing", "grade_diff", "crsid_diff"))
        writer.writerows(
            [diff.mifare_id, diff.crsid, diff.missing, diff.grade_diff, diff.crsid_diff]
            for diff in differences
        )
