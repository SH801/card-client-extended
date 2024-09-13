# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.10] - 2024-08-15

### Changed

- Add pre-commit hooks and reformat code with black and isort

## [1.1.9] - 2024-08-15

### Changed

- Update dependencies and weaken conservative constraints

## [1.1.8] - 2023-10-01

### Changed

- Updated README.md indicating API Gateway apps must be created under a team account.

## [1.1.7] - 2022-09-14

### Fixed

- Updated and corrected documentation.

## [1.1.6] - 2022-02-25

### Fixed

- Ensure that the ordering of output fields is honoured in `export-issued-cards` task.

## [1.1.5] - 2021-12-20

### Added

- Added the ability to specify retry attempts and connect / read timeout.

## [1.1.4] - 2021-11-08

### Fixed

- Update IbisClient to cope with upcoming certificate change in Ibis server.

## [1.1.3] - 2021-10-01

### Fixed

- Fixed an issue with writing files containing unicode characters on systems using non utf-8 encoding.

## [1.1.2] - 2021-08-26

### Fixed

- Fixed installation for py3.6 or lower by resolving dataclasses requirement.

## [1.1.1] - 2021-08-15

### Added

- Added the ability to query for card detail based on identifier and identifier scheme.

## [1.1.0] - 2021-08-15

### Added

- Added the ability to fetch a csv of all issued cards, with incremental updating.

## [1.0.0] - 2021-06-28

### Refactor (stability)

- Use beta1 and alpha2 versions of identity APIs

### Changed

- Use 'visible_name' as column name for the 'full_name' to indicate this may not
  be fully populated.

## [0.1.14] - 2021-06-28

### Fixed

- Ensure that members are filtered out from HR system, this matches functionality
  of the existing card client exports.

## [0.1.13] - 2021-06-28

### Added

- Allow student queries to be filtered by affiliation status.

## [0.1.12] - 2021-06-28

### Added

- Allow querying for recent graduates from the University Student API.

## [0.1.11] - 2021-06-25

### Added

- Allow querying for card using the University HR API's institutions.

## [0.1.9] - 2021-06-13

### Added

- Filter results locally rather than using query parameters, to allow for faster
  responses from the API and filtering across additional values.

### Fixed

- Affiliation status now outputs as `status`, as documented.

## [0.1.8] - 2021-06-21

### Fixed

- Fixed installation of Ibis Client after it has moved.

## [0.1.7] - 2021-06-13

### Added

- Added ability to query cards by student_institution and student_academic_plan
  from the University Student API.

## [0.1.6] - 2021-05-13

### Added

- Added ability to query cards by legacy_carddb_organisation_id

## [0.1.5] - 2021-05-10

### Added

- `forename` and `surname` fields added to export

### Changed

- `name` field renamed to `full_name`

## [0.1.4] - 2021-05-06

### Added

- Added mifare_id_hex to export.

## [0.1.3] - 2021-04-20

### Added

- Fixed ibisclient requirements URL.

## [0.1.2] - 2021-04-19

### Added

- Added the ability to query cards using [LQL](https://www.lookup.cam.ac.uk/lql).

## [0.1.1] - 2021-04-12

### Fixed

- Fixed alternate blank lines when run on Windows.

## [0.1.0] - 2021-02-25

### Added

- Initial version.
