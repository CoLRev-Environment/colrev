suppressPackageStartupMessages(library(bib2df))
suppressPackageStartupMessages(library(dplyr))
suppressPackageStartupMessages(library(plyr))

metadata <- suppressWarnings(bib2df::bib2df("data/references.bib")) %>%
            subset(CATEGORY != 'COMMENT')
screen  <- read.csv("data/screen.csv", encoding = "UTF-8", stringsAsFactors = TRUE)
data  <- read.csv("data/data.csv", encoding = "UTF-8", stringsAsFactors = TRUE)

# Process ---------------------------------

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
                          'series' = 'SERIES',
                          'doi' = 'DOI',
                          'abstract' = 'ABSTRACT',
                          'category' = 'CATEGORY',
                          'book_author' = 'BOOK.AUTHOR',
                          'book_group_author' = 'BOOK.GROUP.AUTHOR',
                          'hash_id' = 'HASH_ID')

metadata$year = as.integer(as.character(metadata$year))

metadata$outlet = ''
metadata$outlet[metadata$category == 'ARTICLE'] = metadata$journal[metadata$category == 'ARTICLE']
metadata$outlet[metadata$category == 'INPROCEEDINGS'] = metadata$booktitle[metadata$category == 'INPROCEEDINGS']


# Duplicates  ----------------------------------

if (0 == nrow(data[duplicated(data$citation_key),])){
  print('ok - check duplicate entries in data.csv$citation_key')
} else {
  print('failed - check duplicate entries in data.csv$citation_key')
  print(data$citation_key[duplicated(data$citation_key)])
  stop('Duplicates in data.csv')
}

if (0 == nrow(metadata[duplicated(metadata$citation_key),])){
  print('ok - check duplicate entries in references.bib$citation_key')
} else {
  print('failed - check duplicate entries in references.bib$citation_key')
  print(metadata$citation_key[duplicated(metadata$citation_key)])
  stop('Duplicates in references.bib')
}

# Value ranges  ----------------------------------

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

check_values(screen, 'inclusion_1', c('no', 'yes'))
check_values(screen, 'inclusion_2', c('no', 'yes'))
for (exclusion_criterion in names(screen)){
  if (grepl('ec_', exclusion_criterion)){
    check_values(screen, exclusion_criterion, c('no', 'yes'))
  }
}


# Dependencies  ----------------------------------

# inclusion_2=yes -> inclusion_1=yes
if (0 == length(screen$citation_key[which(screen$inclusion_2 == 'yes' & screen$inclusion_1 == 'no')])){
  print('ok - inclusion_2=yes -> inclusion_1=yes')
} else {
  print('failed: inclusion_2=yes -> inclusion_1=yes')
  print(screen$citation_key[which(screen$inclusion_2 == 'yes' & screen$inclusion_1 == 'no')])
  stop('Fix data/screen.csv: if inclusion_2=yes, inclusion_1 must be yes.')
}

# inclusion_2 <-> data
if (setequal(data$citation_key, screen$citation_key[which(screen$inclusion_2 == 'yes')])){
  print('ok - check paper$citation_key = screen$citation_key[screen$analyses == yes]')
} else {
  print('failed: check paper$citation_key = screen$citation_key[screen$analyses == yes]')
  print('Missing in entry in data.csv despite screen.csv$inclusion_2=yes:')
  print(setdiff(screen$citation_key[which(screen$inclusion_2 == 'yes')], data$citation_key))
  print('Entry in data.csv despite screen.csv$inclusion_2=no:')
  print(setdiff(data$citation_key, screen$citation_key[which(screen$inclusion_2 == 'yes')]))
  stop('citation_keys in paper.csv and screen (screen=yes) not matching')
}

# If Inclusion_2 is yes, none of the ECs should be violated.

  
for (exclusion_criterion in names(screen)){
  if (grepl('ec_', exclusion_criterion)){
    
    if (0 == nrow(screen[which(screen$inclusion_2 == 'yes' & screen[,exclusion_criterion] != 'no'),])) {
      print(paste('ok - check Inclusion_2=yes -> ', exclusion_criterion,'=no', sep=""))
    } else {
      print(screen$citation_key[which(screen$inclusion_2 == 'yes' & screen[,exclusion_criterion] != 'no')])
      stop(paste('failed - check Inclusion_2=yes -> ', exclusion_criterion,'=no', sep=""))
    }
    
  }
}

# If Inclusion_2 is no, one of the ECs must be violated.
exclusion_criteria_col_indices = grep("^ec_", colnames(screen))
# screen[,exclusion_criteria_col_indices]
# screen[sapply(screen[,exclusion_criteria_col_indices],`==`,e2='no'),]
if (0 == length(screen$citation_key[which(sapply(screen[,exclusion_criteria_col_indices],`!=`,e2='no') & screen$inclusion_2 == 'yes')])) {
  print('ok - check inclusion_2=yes -> no for all exclusion criteria ec_*')
  } else {
    print(screen$citation_key[which(sapply(screen[,exclusion_criteria_col_indices],`!=`,e2='no') & screen$inclusion_2 == 'yes')])
  stop('failed - check inclusion_2=yes -> no for all exclusion criteria ec_*')
}


# Processing ----------------------------------


screen$inclusion_1 <- as.logical(screen$inclusion_1 == 'yes')
screen$inclusion_2 <- as.logical(screen$inclusion_2 == 'yes')


for (exclusion_criterion in names(screen)){
  if (grepl('ec_', exclusion_criterion)){
    
    screen[,exclusion_criterion] <- as.logical(screen[,exclusion_criterion] == 'yes')
    
  }
}

data <- plyr::join(data, metadata, by="citation_key")
rm(metadata, exclusion_criteria_col_indices, exclusion_criterion, check_values)

