from identitylib.identifiers import IdentifierSchemes

# Seeing as we deal directly with Lookup crsid is a fairly special case
# so worth having as a constant
CRSID_SCHEME = str(IdentifierSchemes.CRSID)

identifier_schemes_to_names = {
    CRSID_SCHEME: "crsid",
    str(IdentifierSchemes.USN): "usn",
    str(IdentifierSchemes.STAFF_NUMBER): "staff_number",
    str(IdentifierSchemes.BOARD_OF_GRADUATE_STUDIES): "bgs_id",
    str(IdentifierSchemes.LEGACY_CARDHOLDER): "legacy_card_holder_id",
    str(IdentifierSchemes.MIFARE_ID): "mifare_id",
    str(IdentifierSchemes.MIFARE_NUMBER): "mifare_number",
    str(IdentifierSchemes.LEGACY_CARD): "legacy_card_id",
    str(IdentifierSchemes.PHOTO): "photo_id",
    str(IdentifierSchemes.BARCODE): "barcode",
}

identifier_names_to_schemes = {
    name: scheme for scheme, name in identifier_schemes_to_names.items()
}

identifier_schemes = set(identifier_schemes_to_names.keys())
identifier_names = set(identifier_names_to_schemes.keys())


def id_to_str(value: str, scheme: str):
    # Always deal with identifiers in lower case
    # The case of the identifier used does not matter when calling Lookup or the Card API
    # but when using identifiers as keys within dicts we should ensure that we don't
    # accidentally create duplicates by having identifiers in mixed cases
    return f"{value}@{scheme}".lower()
