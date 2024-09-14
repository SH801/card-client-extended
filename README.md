# Card Client

The Card Client is a command-line tool to allow access and export of data from the Card API.

The Card API exposes data related to university cards, but has no knowledge of institution or group
membership and does not store any personal information related to the people who hold cards.

Therefore this tool uses [Lookup](https://www.lookup.cam.ac.uk/) to allow cards to be queried
by institution or group, and to include basic information about the card holder (currently limited
to name).

For more information about the data exposed through the Card API, refer to the
[Card API's OpenAPI Specification](https://developer.api.apps.cam.ac.uk/docs/card/1/overview).

## Overview

This document gives an overview of how to configure and install the Card Client. We've also
produced a [video which walks through the steps required to install and use the Card Client on Windows](https://web.microsoftstream.com/video/a8ab9500-95de-4662-8247-748e18d46c7e)
(Raven authentication required).

## Installation

### Pre-requisites

To install directly from the repository your machine must have the following programs installed and
available on the `PATH`:

- `python3` & `pip3`
- `git`

Python version 3 can be obtained from the official Python download page [here](https://www.python.org/downloads/),
the installation of `python3` from this source will also install `pip3`.

Git can be obtained from the official Git download page [here](https://git-scm.com/downloads).

To verify these programs are installed at the correct version use the following commands in a terminal:

```bash
python3 --version
# Expected output: Python 3.9.0 (or a higher version).
pip3 --version
# Expected output: pip 21.0.0 (or a higher version).
git --version
# Expected output: git version 2.30.0 (or a higher version).
```

### Standard installation process

The command-line tool can be installed directly from the git repository:

```bash
pip3 install git+https://gitlab.developers.cam.ac.uk/uis/devops/iam/card-database/card-client.git
```

### Alternative installations

The card client can be run using Docker:

```bash
docker run registry.gitlab.developers.cam.ac.uk/uis/devops/iam/card-database/card-client/master:latest
```

For developers, the script can be installed from a cloned repo using pip:

```bash
cd /path/to/this/repo
pip3 install -e .
```

## Usage

The tool offers a three commands:

- `cardclientplus export` which can be used to export data from the Card API to a csv.
- `cardclientplus export-issued-cards` which will generate a csv containing all currently issued cards.
  - `--incremental-update` can be used to incrementally update an existing export with any changes
    since the previous run.
- `cardclientplus card-detail <card_uuid>` which returns a JSON information about the given card by
  card uuid (i.e. the `id` field of a card as returned in an export). Additionally,
  `--identifier-scheme` can be provided in order to allow cards to be queried by any
  identifier referenced by a card. E.g. `cardclientplus card-detail wgd23 --identifier-scheme crsid`
  would return cards for the CRSid wgd23. Supported identifier schemes are listed below under
  `Individual Identifiers`.

A range of configuration options can be set using yaml configuration files which can be provided
using the `--config` or `-c` flags. Multiple configuration files can be provided if necessary, i.e:

```bash
cardclientplus export -c ./configuration.yaml -c ./lookup-credentials.yaml
```

If a configuration path is not given `config.yml` is used by default.

If a valid configuration file is not provided to the program it will not output any useful data, so
users are encouraged to read through the following section carefully and set their configuration
according to their needs.

### Configuration options

An annotated example of the config format is available under
[config.example.yml](config.example.yml), but the following description gives more context on the
options available.

Further configuration examples for specific institutions are provided in the
[example-configuration](example-configuration) directory.

### Authentication

The `environment` section of the configuration allows authentication details to be specified. The
primary means of gaining access to the Card API is through the API Service. Developers
should create a new application and give that application access to the `University Card` product
following the steps described [here](https://developer.api.apps.cam.ac.uk/start-using-an-api).
The credentials for this application should then be included within the `environment` section of
the configuration as `client_key` and `client_secret`.

Applications created in the API Gateway must be created under a team account, any
applications created under a personal account will be denied access to the Card API.

When querying by `legacy_carddb_organisation_id` your application must be granted access to the
`Legacy Cardholder API` within the API Gateway.

When querying by `student_academic_plan`, `student_institution` `recent_graduate_academic_plan`
or `recent_graduate_institution` your application must be granted access to the
`University Student API` within the API Gateway.

When querying by `university_hr_institution` your application must be granted access to the
`University Human Resources API` within the API Gateway.

#### `environment` (required)

##### `environment.client_key`

The client key of the application created within the API Service which will give access to the Card
API.

##### `environment.client_secret`

The client secret of the application created within the API Service which will give access to the
Card API.

##### `environment.base_url` (optional)

Used to set the base url of the Card API to be used by the tool. By default this tool will use the
production deployment of the Card API (https://api.apps.cam.ac.uk/card).

##### `environment.timeout` (optional)

The http connect and read timeout that is used when requesting data (in seconds), default `10`.

##### `environment.retry_attempts` (optional)

The number of times to retry a failed request to any of the APIs used by the card client, default
`3`.

#### `lookup_credentials`

`username` and `password` dictionary of credentials to use to query Lookup. The `username` should
correspond to the name of the group being used to authenticate, with the `password` being the
password generated for that group. The Lookup documentation gives
[more detail about generating Lookup group credentials](https://help.uis.cam.ac.uk/service/collaboration/lookup/groups).

When using the card client outside the CUDN, Lookup credentials must be used when fetching data
by `lookup_group`, `lookup_institution` or `crsid`. If these credentials are not set and the tool
is used outside the CUDN or the credentials are not valid, the tool will error with a
`ibisclient.connection.IbisException`.

Lookup credentials can additionally be used to ensure that all members of a group or Lookup
institution are returned, where the membership visibility of members within an institution or group
is below `University`. This can be achieved by adding the group that is being used to authenticate
to the group or institution's managers group. This allows the card client to act as a group manager
and view all members of a given group or institution.

#### `filter` (can also be used as deprecated `params`)

A dictionary of fields to filter by value, only cards with fields matching the values
provided will be included in the export.

For example, the following configuration would only include cards with the status
`ISSUED` and the issueNumber `1`.

```yml
filter:
  status: ISSUED
  issueNumber: 1
```

The `status` filter item is the most important, and in most cases to get a list of valid cards to be
considered for access the filter should be set to:

```yml
filter:
  status: ISSUED
```

##### Card States

The ISSUED card state denotes cards that are currently in use, and this is the card state that will
need to be considered in most cases. For further guidance on the different card states refer to the
underlying Card API documentation, found [on the API gateway](https://developer.api.apps.cam.ac.uk/docs/card/1/overview).

#### `queries` (required)

The `queries` block allows you to specify which cards need to be included in the export. Multiple
queries can be included in the configuration, allowing data to be fetched from different sources.

**Example:**

```yaml
queries:
  - by: lookup_institution
    ids:
      - UIS
      - ENG
    extra_fields_for_results:
      fetched_by_institution: True
  - by: crsid
    id: wgd23
    extra_fields_for_results:
      fetched_by_institution: False
```

This example shows two queries, the first will get cards for all people within the Lookup
institutions `UIS` and `ENG`. The second will get all cards for the crsid `wdg23`.

##### `query.by`

Each query must contain a `by` property which specifies where data shall be fetched from.

###### Lookup

Data can be exported via Lookup Group or Lookup Institution using the options:

- `lookup_institution` - fetch data by Lookup institution (allows `name` to be included in the export)
- `lookup_group` - fetch data by Lookup group (allows `name` to be included in the export)
- `lql` - fetch data by searching Lookup using [LQL](https://www.lookup.cam.ac.uk/lql).
  - Note that instead of providing `id` or `ids` you should instead provide a `lql_query` containing
    the query to be run. See the example under `query.lql_query` below.

###### Student institution and Academic Plan (CamSIS)

Data can also be exported by `student_institution` or `student_academic_plan`, which fetches cards
for students using either their CamSIS campus or department (when querying by `student_institution`)
or their CamSIS academic plan (when querying by `student_academic_plan`). This allows you to export
all cards for all students within a CamSIS college, or all cards for all students undertaking a
given academic plan.

Querying by `student_institution` or `student_academic_plan` only returns students who are
currently undertaking a course within CamSIS. Because this can lead to students having their
access to facilities cut-off within the summer-months when they are technically not undertaking a
course of study, recent graduates can be queried using `recent_graduate_institution` and
`recent_graduate_academic_plan`. This returns students who have finished a course within a given
institution or academic plan **within the last 6 months**.

When querying by any of the above, the client returns cardholders from CamSIS groups via the
University Student API. An `affiliation_status` field is included containing the cardholder's
status within the given institution or academic plan. The `affiliation_status` field is a
representation of the Academic Career held in CamSIS. For further details see the
[University Student API documentation](https://developer.api.apps.cam.ac.uk/docs/university-student/1/overview).

Students with different statuses can be filtered by providing an `affiliation_status` within the
query, this status should be
[one of the `Academic Careers` returned from CamSIS](https://www.camsis.cam.ac.uk/files/student-codes/d05.html).
For example, the following query only returns postgraduates for a given college:

```yaml
queries:
  - by: recent_graduate_institution
    id: EM
    affiliation_status: PGRD
```

###### University HR institution (CHRIS)

Data can also be exported by `university_hr_institution` which fetches cards for people based on
their department or college within CHRIS. This allows you to export all cards for all staff members
within a given department or college within CHRIS.

###### Legacy cardholder organisation

Data can also be exported by `legacy_carddb_organisation_id`, this allows cardholders to be
fetched using their affiliated organisation id from the legacy card system. Only cardholders
who do not have a CRSid, Staff Number, or USN will be returned, as this method of querying is
simply to allow access to cardholders who do not exist within other identity systems (e.g.
Lookup, CamSIS or CHRIS).

###### Individual identifiers

Data can also be fetched by the following identifiers:

- `crsid`
- `usn`
- `staff_number`
- `bgs_id`
- `legacy_card_holder_id`
- `mifare_id`
- `mifare_number`
- `legacy_card_id`
- `photo_id`
- `barcode`

**Note** where data is fetched from Lookup, `student_institution`,
`student_academic_plan`, `university_hr_institution` or `legacy_carddb_organisation_id` a
limited set of personal information can be included in the export (currently `visible_name`,
`forenames` and `surname` are included).

##### `query.id` or `query.ids`

The `id` or `ids` properties allows you to specify the ids of the entity you want to query by. For
example, if you needed to query by a set of `usn`s you would list them under `ids` with `by` set to
`usn`.

##### `query.lql_query`

When setting `by` to `lql` you must populate `lql_query` with a valid person
[LQL](https://www.lookup.cam.ac.uk/lql) query. LQL queries are limited to searching for people,
as people must be returned from Lookup for the script to fetch their cards. Therefore the
`person: ` prefix is optional at the start of a query. Below is an example of a query that finds
all cards for people within UIS who are staff members:

```yaml
queries:
  - by: lql
    lql_query: "IN INST (UIS) and misAffiliation = staff"
```

##### `extra_fields_for_results`

The `extra_fields_for_results` property allows you to specify an additional column which will be
included in the export - with the values set to whatever you specify within each query. This is
useful if you need to group certain cards together within the export based on how they were
queried.

**Example:**

```yaml
queries:
  - by: lookup_institution
    ids:
      - UIS
      - ENG
    extra_fields_for_results:
      fetched_by_institution: True
  - by: crsid
    id: wgd23
    extra_fields_for_results:
      fetched_by_institution: False
```

In the example above we simply add a flag to each query indicating how the data was queried by
adding the `fetched_by_institution` entry. This will add the column to our csv export, with each
card that is fetched by a given query getting the value of `fetched_by_institution` as specified in
that query.

#### `output`

Allows the output location and fields to be configured.

##### `output.file` (defaults to `export.csv`)

The location where the export file should be written.

##### `output.deduplicate` (defaults to `False`)

Whether to remove duplicates from the export - duplicates are determined by `card.id` so although
some cards may have identical information, if they have different ids they will still be included
in the export.

**Note** when a duplicate is encountered, the first card record is retained and any subsequent
duplicates are dropped. This means that if two queries return the same card, the card will be
present in the block of cards returned for the first query and not the block of cards returned in
the second query. This means that if `extra_fields_for_results` are included in either query,
only the `extra_fields_for_results` for the first query will be present on the card entry.
Therefore, when setting `deduplicate: True` and using `extra_fields_for_results`, queries should
be ordered with the understanding that any card records which are returned from multiple queries
will have the `extra_fields_for_results` from the first query they match applied.

##### `output.fields`

The fields that should be included in the export. This allows you to exclude certain information
from being included within the csv and re-order the headings of the csv file that is written. By
default all fields that exist on a card entry are written, as well as any additional fields
specified by `extra_fields_for_results`.

When not specifying `output.fields` the order of the columns in the csv is likely to change with
each export, so you should not rely on data being in a specific column index and instead always
read the column headers.

##### Default fields

By default the following fields are included within the exports of card data:

- `visible_name` - what is visible of the full name of the cardholder from the upstream identity
  system, in the case of Lookup this depends on what a person has made visible
  within their Lookup profile.
- `forenames` - the forenames of the cardholder. When data is fetched from Lookup this may not be
  populated. When data is fetched by legacy cardholder organisation this will not be
  populated.
- `surname` - the surname of the cardholder.
- `affiliation_status` - when data is fetched by `student_institution` or `student_academic_plan`
  this will be set to the academic plan of the cardholder, see
  https://www.camsis.cam.ac.uk/files/student-codes/d05.html for the
  possible values of this.
- `issuedAt` - an ISO 8601 datetime representing when this card was issued.
- `issueNumber` - the issue number of this card.
- `expiresAt` - an ISO 8601 datetime representing when this card expires.
- `revokedAt` - an ISO 8601 datetime representing when this card was revoked.
- `returnedAt` - an ISO 8601 datetime representing when this card was returned.
- `status` - the status of this card - can be one of: `ISSUED`, `REVOKED`, `RETURNED`, `EXPIRED`.
- `cardType` - the type of this card - can be one of: `MIFARE_PERSONAL`, `MIFARE_TEMPORARY`.
  Given how cards are queried using the card client it is very rare that temporary
  cards will be returned.
- `id` - the UUID of this card record used to identify this card within the Card API.
- `crsid` - the CRSid of the cardholder.
- `usn` - the USN of the cardholder.
- `staff_number` - the staff number of the cardholder.
- `bgs_id` - the board of graduate studies identifier of the cardholder.
- `legacy_card_holder_id` - the identifier of the cardholder within the legacy card system.
- `legacy_card_id` - the identifier of the card within the legacy card system.
- `mifare_id` - a decimal representation of the mifare identifier embedded within this card.
  This value is not padded with leading zeros.
- `mifare_id_hex` - a hex representation of the mifare identifier embedded within this card.
- `mifare_number` - the mifare number embedded within this card.
- `barcode` - the barcode printed on this card.
- `photo_id` - the UUID of the photo printed on this card. This can be used to fetch the photo
  of the cardholder which has been used on this card from the University Photo API.
- `updatedAt` - an ISO 8601 datetime representing when this card was last updated within the
  Card API.

##### Extended fields - Card client 'plus'
- `lastnote` - last note on card record
- `lastnoteAt` - date of last note on card record

