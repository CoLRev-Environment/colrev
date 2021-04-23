suppressPackageStartupMessages(library(xtable))
suppressPackageStartupMessages(library(data.table))

source('analyses/load_data.R')

SearchMetrics <- data.frame(search_type = character(),
                            precision = character(),
                            recall = character(),
                            percentage_identified = character(),
                            uniquely_identified = character())

precision <- function(matrix){
  diag = diag(matrix)
  colsums = apply(matrix, 2, sum)
  return(diag / colsums)
}

recall <- function(matrix){
  diag = diag(matrix)
  rowsums = apply(matrix, 1, sum)
  return(diag / rowsums)
}

paper$inclusion_2[is.na(paper$inclusion_2)] <- FALSE

total_nr_papers <- nrow(paper[paper$inclusion_2,])

table_toc <- table(paper$inclusion_2, paper$search.toc)
SearchMetrics <- rbind(SearchMetrics,
                       data.frame(search_type = 'Table-of-content search',
                                  precision = toString(format(precision(table_toc)['TRUE'], digits = 3)),
                                  recall = toString(format(recall(table_toc)['TRUE'], digits = 3)),
                                  percentage_identified = toString(paste(round(nrow(paper[paper$search.toc &
                                                                                            paper$inclusion_2,])/total_nr_papers*100, 2), "\\%", sep="")),
                                  uniquely_identified = toString(nrow(paper[paper$search.toc &
                                                                                      paper$inclusion_2 &
                                                                                      !paper$search.db.google.scholar &
                                                                                      !paper$search.db.ais.library &
                                                                                      !paper$search.complementary,]))))

table_gs <- table(paper$inclusion_2, paper$search.db.google.scholar)
SearchMetrics <- rbind(SearchMetrics,
                       data.frame(search_type = 'Database search (Google Scholar)',
                                  precision = toString(format(precision(table_gs)['TRUE'], digits = 3)),
                                  recall = toString(format(recall(table_gs)['TRUE'], digits = 3)),
                                  percentage_identified = toString(paste(round(nrow(paper[paper$search.db.google.scholar &
                                                                                      paper$inclusion_2,])/total_nr_papers*100, 2), "\\%", sep="")),
                                  uniquely_identified = toString(nrow(paper[paper$search.db.google.scholar &
                                                                              paper$inclusion_2 &
                                                                              !paper$search.db.ais.library &
                                                                              !paper$search.toc &
                                                                              !paper$search.complementary,]))))

table_ais <- table(paper$inclusion_2, paper$search.db.ais.library)
SearchMetrics <- rbind(SearchMetrics,
                       data.frame(search_type = 'Database search (AISeL)',
                                  precision = toString(format(precision(table_ais)['TRUE'], digits = 3)),
                                  recall = toString(format(recall(table_ais)['TRUE'], digits = 3)),
                                  percentage_identified = toString(paste(round(nrow(paper[paper$search.db.ais.library &
                                                                                            paper$inclusion_2,])/total_nr_papers*100, 2), "\\%", sep="")),
                                  uniquely_identified = toString(nrow(paper[paper$search.db.ais.library &
                                                                       paper$inclusion_2 &
                                                                       !paper$search.db.google.scholar &
                                                                       !paper$search.toc &
                                                                       !paper$search.complementary,]))))

table_complementary <- table(paper$inclusion_2, paper$search.complementary)
SearchMetrics <- rbind(SearchMetrics,
                       data.frame(search_type = 'Complementary search',
                                  precision = toString(format(precision(table_complementary)['TRUE'], digits = 3)),
                                  recall = toString(format(recall(table_complementary)['TRUE'], digits = 3)),
                                  percentage_identified = toString(paste(round(nrow(paper[paper$search.complementary &
                                                                                            paper$inclusion_2,])/total_nr_papers*100, 2), "\\%", sep="")),
                                  uniquely_identified = toString(nrow(paper[paper$search.complementary &
                                                                              paper$inclusion_2 &
                                                                              !paper$search.db.google.scholar &
                                                                              !paper$search.db.ais.library &
                                                                              !paper$search.toc,]))))

SearchMetrics$precision <- round(as.numeric(as.character(SearchMetrics$precision)), digits = 2)
SearchMetrics$recall    <- round(as.numeric(as.character(SearchMetrics$recall)), digits = 2)

SearchMetrics <- data.table::setnames(SearchMetrics, old = "recall", new = "{Recall}")
SearchMetrics <- data.table::setnames(SearchMetrics, old = "precision", new = "{Precision}")
SearchMetrics <- data.table::setnames(SearchMetrics, old = "search_type", new = "Search Type")
SearchMetrics <- data.table::setnames(SearchMetrics, old = "percentage_identified", new = "Percentage identified")
SearchMetrics <- data.table::setnames(SearchMetrics, old = "uniquely_identified", new = "{Uniquely identified}")

SearchMetricsTeX <- xtable::xtable(SearchMetrics,
                            caption = 'Search metrics',
                            label = 'tab:search-metrics', # insert here Latex reference for this table
                            align = c('l', 'l', 'S[table-number-alignment = center]', 'S[table-number-alignment = center]', 'r', 'S[table-number-alignment = center]'))

xtable::print.xtable(SearchMetricsTeX, file = getOption("xtable.file", "output/search-metrics.tex"),
                     # add.to.row = add.to.row,
                     caption.placement = getOption("xtable.caption.placement", "top"),
                     floating.environment = "table",
                     table.placement = "h",
                     hline.after = getOption("xtable.hline.after", c(-1, 0, 4)),
                     include.rownames = getOption("xtable.include.rownames", FALSE),
                     # booktabs = getOption("xtable.booktabs", TRUE),
                     comment = getOption("xtable.comment", FALSE),
                     timestamp = getOption("xtable.timestamp", FALSE),
                     sanitize.text.function = function(x){x})
