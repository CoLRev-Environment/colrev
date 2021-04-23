# Install git, Docker, LibreOffice

TODO: include description.

# Configure LibreOffice

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


# Dockerfile and repository structure


```
cd analysis
docker build -t python3_review_template .

```

The analyses are implemented in R and Python. The [Dockerfile](Dockerfile) contains necessary dependencies to make the analyses reproducible. Instructions for  [installing](https://docs.docker.com/install/linux/docker-ce/ubuntu/)  and [configuring](https://docs.docker.com/install/linux/linux-postinstall/) [Docker](https://www.docker.com/) are available online. The Rstudio image extended here is based on the [Rocker project](https://github.com/rocker-org/rocker-versioned/tree/master/rstudio). Further help regarding the use and extension of a Rocker image can be found [here](https://www.rocker-project.org/).  
```Shell
# build the image {wur_rstudio} from the Dockerfile
docker build -t wur_rstudio .
# docker container start command (~/git assumes that the git repositories are stored in the user's home directory, i.e. /home/{USER}/git)
docker run --rm -p 8787:8787 -v ~/git:/home/rstudio wur_rstudio
```
RStudio can now be accessed through the browser:
```Shell
http://localhost:8787/
username: rstudio
password: rstudio
```
The terminal/bash of the current container can be accessed as follows:
```Shell
# list the CONTAINER_ID of the current container (changes with every container start)
docker ps
# insert CONTAINER_ID to switch bash to docker container bash:
docker exec -it {CONTAINER_ID} bash
```
All data-transformations and analyses are included in the [Makefile](Makefile):
```Shell
make run
# to build parts of the analyses, (remove the last backslash that is added by auto-completion):
make 2-technically-correct-data
# to force rebuilding:
make -B 4-results
```
