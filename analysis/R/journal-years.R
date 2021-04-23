source('analyses/load_data.R')

# imputation of missing years
paper$YEAR = factor(paper$YEAR, levels=seq(min(paper$YEAR),max(paper$YEAR),1))

freq_table <- table(paper$JOURNAL, paper$YEAR)
freq_table <- addmargins(freq_table, c(1, 2), FUN=sum)

freq_table <- cbind(JOURNAL = rownames(freq_table), freq_table)

write.table(freq_table, file = "output/journal-years-table.csv",
            sep = ",", col.names = TRUE, row.names = FALSE, qmethod = "double", fileEncoding = "UTF-8")
