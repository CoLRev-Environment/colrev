# Setup

The pipeline is implemented in a Docker-compose environment, ensuring cross-platform compatibility.

# Install Docker-compose and Docker

The analyses are implemented in Python.
Instructions for  [installing](https://docs.docker.com/install/linux/docker-ce/ubuntu/)  and [configuring](https://docs.docker.com/install/linux/linux-postinstall/) [Docker](https://www.docker.com/) and [Docker-compose](https://docs.docker.com/compose/install/) are available online.

Git and make are available in the Docker container.

# Setup JabRef (hash-id compatible)

This is a modified version of JabRef that preserves hash-ids when merging records.

```
git clone --depth=10 https://github.com/geritwagner/jabref.git
cd jabref
./gradlew assemble
./gradlew run

```

Based on [JabRef instructions](https://devdocs.jabref.org/getting-into-the-code/guidelines-for-setting-up-a-local-workspace).

# Install and configure LibreOffice

Install LibreOffice

In LibreOfficeCalc: set the following default parameters for CSV files (or manually select them everytime when opening/importing and saving a csv file through the "edit filter settings" dialogue) via Tools > Options > LibreOffice > advanced > Open Expert Configuration:

- CSVExport/TextSeparator: "
- CSVExport/FieldSeparator: ,
- CSVExport/QuoteAllTextCells: true
- CSVImport/QuotedFieldAsText: true
