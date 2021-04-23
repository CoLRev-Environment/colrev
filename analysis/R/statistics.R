source('analyses/load_data.R')

SearchStatistics <- data.frame(search_type = character(),
                            papers_identified = character())


SearchStatistics <- rbind(SearchStatistics,
                          data.frame(search_type = 'Database search (Google Scholar)',
                          papers_identified = toString(format(nrow(paper[paper$search.db.google.scholar,]), digits = 3))))


SearchStatistics <- rbind(SearchStatistics,
                          data.frame(search_type = 'Database search (AISeL)',
                          papers_identified = toString(format(nrow(paper[paper$search.db.ais.library,]), digits = 3))))

SearchStatistics <- rbind(SearchStatistics,
                          data.frame(search_type = 'Comlementary search',
                          papers_identified = toString(format(nrow(paper[paper$search.complementary,]), digits = 3))))


write.table(SearchStatistics, file = "output/search_statistics.csv", sep = ",", col.names = TRUE,
            row.names = FALSE, qmethod = "double", fileEncoding="UTF-8")



source('analyses/load_data.R')

paper <- paper[which(paper$inclusion_2),] %>% subset(select = -c(search.db.google.scholar,
                                                                 search.db.ais.library,
                                                                 search.toc,
                                                                 search.complementary,
                                                                 inclusion_1,
                                                                 inclusion_2,
                                                                 inclusion_2_criterion1,
                                                                 inclusion_2_criterion2,
                                                                 inclusion_2_comment,
                                                                 CATEGORY,
                                                                 AUTHOR,
                                                                 BOOKTITLE,
                                                                 JOURNAL,
                                                                 NUMBER,
                                                                 PAGES,
                                                                 SERIES,
                                                                 TITLE,
                                                                 VOLUME,
                                                                 YEAR))
write.table(paper,
            file = 'output/data_extraction.csv',
            sep = ",",
            col.names = TRUE,
            row.names=FALSE,
            qmethod = "double",
            fileEncoding="UTF-8")
