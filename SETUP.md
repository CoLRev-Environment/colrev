# Setup

# git

Install git

# Configure LibreOffice

Install LibreOffice

LibreOfficeCalc: set the following default parameters for CSV files (or manually select them everytime when opening/importing and saving a csv file through the "edit filter settings" dialogue) via Tools > Options > LibreOffice > advanced > Open Expert Configuration:
- CSVExport/TextSeparator: "
- CSVExport/FieldSeparator: ,
- CSVExport/QuoteAllTextCells: true
- CSVImport/QuotedFieldAsText: true


# Setup JabRef (hash-id compatible)

```
git clone --depth=10 https://github.com/geritwagner/jabref.git
cd jabref
./gradlew assemble
./gradlew run

```

Based on [JabRef instructions](https://devdocs.jabref.org/getting-into-the-code/guidelines-for-setting-up-a-local-workspace).

# Dockerfile

```
cd analysis
docker build -t python3_review_template .
```

The analyses are implemented in R and Python.
The [Dockerfile](Dockerfile) contains necessary dependencies to make the pipeline reproducible.
Instructions for  [installing](https://docs.docker.com/install/linux/docker-ce/ubuntu/)  and [configuring](https://docs.docker.com/install/linux/linux-postinstall/) [Docker](https://www.docker.com/) are available online.
