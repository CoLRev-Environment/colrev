suppressPackageStartupMessages(library(bib2df))
suppressPackageStartupMessages(library(dplyr))
suppressPackageStartupMessages(library(plyr))

paper  <- read.csv("data/paper_coding.csv", encoding = "UTF-8", stringsAsFactors = TRUE)
metadata <- suppressWarnings(bib2df::bib2df("data/paper.bib")) %>%
            subset(CATEGORY != 'COMMENT')
metadata <- dplyr::select(metadata,
                          -one_of(names(metadata)[names(metadata) %in% c('ADDRESS',
                                                                         'ANNOTE',
                                                                         'CHAPTER',
                                                                         'CROSSREF',
                                                                         'EDITION',
                                                                         'EDITOR',
                                                                         'HOWPUBLISHED',
                                                                         'INSTITUTION',
                                                                         'KEY',
                                                                         'MONTH',
                                                                         'NOTE',
                                                                         'ORGANIZATION',
                                                                         'PUBLISHER',
                                                                         'SCHOOL',
                                                                         'TYPE',
                                                                         'ISSN',
                                                                         'RESEARCHERID.NUMBERS',
                                                                         'VENUE',
                                                                         'FUNDING.ACKNOWLEDGEMENT',
                                                                         'FUNDING.TEXT')]))

metadata <- dplyr::rename(metadata, 'citation_key' = 'BIBTEXKEY',
                              'journal' = 'JOURNAL',
                              'year' = 'YEAR',
                              'author' = 'AUTHOR',
                              'title' = 'TITLE',
                              'number' = 'NUMBER',
                              'pages' = 'PAGES',
                              'volume' = 'VOLUME',
                              'booktitle' = 'BOOKTITLE',
                              'category' = 'CATEGORY',
                              'series' = 'SERIES',
                              'keywords' = 'KEYWORDS',
                              'file' = 'FILE')

metadata$year = as.integer(as.character(metadata$year))

metadata$outlet = ''
metadata$outlet[metadata$category == 'ARTICLE'] = metadata$journal[metadata$category == 'ARTICLE']
metadata$outlet[metadata$category == 'INPROCEEDINGS'] = metadata$booktitle[metadata$category == 'INPROCEEDINGS']

# Checks ----------------------------------

if (setequal(paper$citation_key, metadata$citation_key)){
  print('ok: check paper.bib$citation_key = paper_coding.csv$citation_key')
} else {
  print('failed: check paper.bib$citation_key = paper_coding.csv$citation_key')
  print('Missing in bibliography/metadata:')
  print(setdiff(paper$citation_key, metadata$citation_key))
  print('Missing in coding sheet:')
  print(setdiff(metadata$citation_key, paper$citation_key))
  stop('citation_keys in paper.csv and paper_coding.csv not matching')
}

if (0 == nrow(paper[duplicated(paper$citation_key),])){
  print('ok - check duplicate entries in paper_coding.csv$citation_key')
} else {
  print('failed - check duplicate entries in paper_coding.csv$citation_key')
  print(paper$citation_key[duplicated(paper$citation_key)])
  stop('Duplicates in paper_coding.csv')
}

if (0 == nrow(metadata[duplicated(metadata$citation_key),])){
  print('ok - check duplicate entries in paper.bib$citation_key')
} else {
  print('failed - check duplicate entries in paper.bib$citation_key')
  print(metadata$citation_key[duplicated(metadata$citation_key)])
  stop('Duplicates in paper.bib')
}

# value ranges

check_values <- function(input_df, column_name, admissible_values){
  admissible_value_string = paste(admissible_values, collapse = ',')
  if (setequal(levels(input_df[,column_name]), admissible_values)){
    print(paste('ok - check ', column_name, 'in (', admissible_value_string, ')'), sep="")
  } else {
    print(paste('failed - check ', name, 'in (', admissible_value_string, ')'), sep="")
    print(input_df[!(input_df[,column_name] %in% admissible_values),c('citation_key', column_name)])
    stop('stopped')
  }
}

check_values(paper, 'search_db_ais_library', c('no', 'yes'))
check_values(paper, 'search_db_google_scholar', c('no', 'yes'))
check_values(paper, 'search_toc', c('no', 'yes'))

# dependencies

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'yes' & paper$Inclusion_1 == 'no'))) {
  print('ok - check Inclusion_2=yes -> NOT Inclusion_1=no')
} else {
  stop('failed - check Inclusion_2=yes -> NOT Inclusion_1=no')
}

# If Inclusion_2 is yes, none of the ECs can be violated.

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'yes' & paper$Inclusion_2_EC1 == 'no'))) {
  print('ok - check Inclusion_2=yes -> NOT Inclusion_2_EC1=no')
} else {
  stop('failed - check Inclusion_2=yes -> NOT Inclusion_2_EC1=no')
}

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'yes' & paper$Inclusion_2_EC2 == 'no'))) {
  print('ok - check Inclusion_2=yes -> NOT Inclusion_2_EC2=no')
} else {
  stop('failed - check Inclusion_2=yes -> NOT Inclusion_2_EC2=no')
}

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'yes' & paper$Inclusion_2_EC3 == 'no'))) {
  print('ok - check Inclusion_2=yes -> NOT Inclusion_2_EC3=no')
} else {
  stop('failed - check Inclusion_2=yes -> NOT Inclusion_2_EC3=no')
}

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'yes' & paper$Inclusion_2_EC4 == 'no'))) {
  print('ok - check Inclusion_2=yes -> NOT Inclusion_2_EC4=no')
} else {
  stop('failed - check Inclusion_2=yes -> NOT Inclusion_2_EC4=no')
}

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'yes' & paper$Inclusion_2_EC5 == 'no'))) {
  print('ok - check Inclusion_2=yes -> NOT Inclusion_2_EC5=no')
} else {
  stop('failed - check Inclusion_2=yes -> NOT Inclusion_2_EC5=no')
}

# If Inclusion_2 is no, one of the ECs must be violated.

if (0 == nrow(subset(paper, paper$Inclusion_2 == 'no' & paper$Inclusion_2_EC1 == 'yes' &
                paper$Inclusion_2_EC2 == 'yes' &
                paper$Inclusion_2_EC3 == 'yes' &
                paper$Inclusion_2_EC4 == 'yes' &
                paper$Inclusion_2_EC5 == 'yes'))) {
  print('ok - check Inclusion_2=no -> NOT yes for all Inclusion_2_EC*')
  } else {
  stop('failed - check Inclusion_2=no -> NOT yes for all Inclusion_2_EC*')
}

#TODO data extracted = yes -> Inclusion2 yes


# Processing ----------------------------------

check_values(paper, 'search_db_ais_library', c('no', 'yes'))
check_values(paper, 'search_db_google_scholar', c('no', 'yes'))
check_values(paper, 'search_toc', c('no', 'yes'))


paper$Inclusion_1 <- as.logical(paper$Inclusion_1 == 'yes')
paper$search_db_ais_library <- as.logical(paper$search.db.google.scholar == 'yes')
paper$search_db_google_scholar <- as.logical(paper$search.db.ais.library == 'yes')
paper$search_toc <- as.logical(paper$search.db.abi.informs == 'yes')

paper$Inclusion_2 <- as.logical(paper$Inclusion_2 == 'yes')
paper$Inclusion_2_EC1 <- as.logical(paper$Inclusion_2_EC1 == 'yes')
paper$Inclusion_2_EC2 <- as.logical(paper$Inclusion_2_EC2 == 'yes')
paper$Inclusion_2_EC3 <- as.logical(paper$Inclusion_2_EC3 == 'yes')
paper$Inclusion_2_EC4 <- as.logical(paper$Inclusion_2_EC4 == 'yes')
paper$Inclusion_2_EC5 <- as.logical(paper$Inclusion_2_EC5 == 'yes')
paper$Inclusion_2[is.na(paper$Inclusion_2)] <- FALSE

#TODO: other columns (data extraction)

paper$data_extraction <- FALSE
paper$data_extraction[paper$Inclusion_2] <- TRUE

paper <- plyr::join(paper, metadata, by="citation_key")
rm(metadata)

# Inclusion_1 FALSE -> no file linked
if (0 == nrow(subset(paper, !paper$Inclusion_1 & !(is.na(paper$file))))) {
  print('ok - check Inclusion_1=no -> no file linked')
} else {
  print(subset(paper, !paper$Inclusion_1 & !(is.na(paper$file))))
  stop('failed - check Inclusion_1=no -> no file linked')
}

# Inclusion_1 TRUE -> file linked
if (0 == nrow(subset(paper, paper$Inclusion_1 & is.na(paper$file)))) {
  print('ok - check Inclusion_1=yes -> file linked')
} else {
  print(subset(paper, paper$Inclusion_1 & is.na(paper$file)))
  stop('failed - check Inclusion_1=yes -> file linked')
}
