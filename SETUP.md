# Setup

To set the repository up, execute the following commands to create a git-versioned data directory:

```
mkdir data
cd data
git init
mkdir search
mkdir pdfs
```

# Install git

Install git following the [instructions](https://git-scm.com/) available online.

# Install Docker and build container

The analyses are implemented in Python and R.
The Dockerfiles ([1](analysis/Dockerfile), [2](analyses/R/Dockerfile)) contain necessary dependencies to make the pipeline reproducible.
Instructions for  [installing](https://docs.docker.com/install/linux/docker-ce/ubuntu/)  and [configuring](https://docs.docker.com/install/linux/linux-postinstall/) [Docker](https://www.docker.com/) are available online.

To build the container, run

```
cd analysis
docker build -t review_template_python3 .
cd R
docker build -t review_template_R .
```

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
