source('analysis/R/load_data.R')
source('analysis/R/figure_defaults.R')
suppressPackageStartupMessages(library(tidyverse))

# Journal-years table -------------------------------------

freq_table <- table(data$journal, data$year)
freq_table <- addmargins(freq_table, c(1, 2), FUN=sum)

freq_table <- cbind(journal = rownames(freq_table), freq_table)

write.table(freq_table, file = "output/journal-years-table.csv",
            sep = ",", col.names = TRUE, row.names = FALSE, qmethod = "double", fileEncoding = "UTF-8")


# Timeline plot -------------------------------------------


papers_included_years <- plyr::count(subset(data, year > 1980 & year < 2025), vars = c('year'))

# imputation: show data from 2000 to 2019
for (i in min(papers_included_years$year):max(papers_included_years$year)) {
  if (nrow(papers_included_years[papers_included_years$year == i,]) == 0) {
    papers_included_years <- rbind(papers_included_years, data.frame(year = i, freq = 0))
  }
}

papers_included_years$year <- as.numeric(papers_included_years$year)
papers_included_years <- plyr::arrange(papers_included_years, year)
labels_years <- seq(min(papers_included_years$year), max(papers_included_years$year), 1)

labels_nr_lrs <- seq(0,11,1)
papers_included_years2 <- papers_included_years %>%
  select(year, freq) %>%
  do(as.data.frame(spline(x = .[['year']], y = .[['freq']], n = nrow(.)*20)))
papers_timeline <- ggplot(papers_included_years, aes(x = year, y = freq)) +
  geom_line(data = papers_included_years2, aes(x = x, y = y), size = 0.7) +
  geom_point(shape = 15, size = 1.5) +
  scale_color_manual(values = c("black", "grey60")) +
  scale_x_continuous(breaks = labels_years, labels = labels_years) +
  scale_y_continuous(labels = labels_nr_lrs, breaks = labels_nr_lrs) +
  aes(ymin = 0) +
  xlab("") + ylab("Number of Papers") +
  general_theme +
  theme(panel.grid.major = element_line(colour = "grey60"),
        plot.margin = unit(c(0.1,0.1,-0.2,0.1),"cm"),
        legend.position = c(0.17,0.82),
        legend.title = element_blank(),
        legend.text = element_text(size = font_size*0.9, family = custom_font),
        legend.background = element_rect(fill = "white", color = "black", size = 0.6, linetype = "solid"),
        axis.line = element_line(colour = "black", size = 1.1, linetype = "solid"),
        panel.border = element_rect(linetype = 'solid', colour = "grey60", size = 0.8),
        axis.ticks = element_line(colour = "black", size = 1, linetype = "solid"),
        axis.ticks.length = unit(0.13, "cm")
  )

# tikzDevice::tikz('output/timeline.tex', width = 6.3, height = 1.7, timestamp = FALSE)
pdf('output/timeline.pdf', width=6, heigh=2)
plot(papers_timeline)
dev.off()

# PRISMA diagram ------------------------------------------------------

font_size = 3

search_details  <- read.csv("data/search/search_details.csv", encoding = "UTF-8", stringsAsFactors = TRUE)

total_results_from_search = sum(search_details$number_records)

records_screened = nrow(screen)
duplicates_removed = total_results_from_search - records_screened

exclusion1 = nrow(screen[!screen$inclusion_1,])
full_text_articles_retrieved = nrow(screen[screen$inclusion_1,])

exclusion2 = nrow(screen[which(!screen$inclusion_2),])

print('TODO: ')
# inclusion_2_criterion1 = nrow(data[!data$inclusion_2_criterion1,])
# inclusion_2_criterion2 = nrow(data[!data$inclusion_2_criterion2,])

articles_indluded_in_synthesis = nrow(data)

format_statistics <- function(statistic){
  return(format(round(statistic), nsmall = 0, big.mark = ","))
}

data <- tibble(x = 1:100, y = 1:100)
p <- data %>%
  ggplot(aes(x, y)) +
  scale_x_continuous(minor_breaks = seq(10, 100, 10)) +
  scale_y_continuous(minor_breaks = seq(10, 100, 10), limits = c(10,100)) +
  theme_linedraw() +
  expand_limits(y=10)


p <- p +
  geom_rect(xmin = 0, xmax = 5, ymin = 75, ymax = 100, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 2.5, y = 87.5, label = 'Identification', size = font_size, angle = 90)

p <- p +
  geom_rect(xmin = 0, xmax = 5, ymin = 35.5, ymax = 73, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 2.5, y = 55, label = 'Paper Selection', size = font_size, angle = 90)

p <- p +
  geom_rect(xmin = 10, xmax = 30, ymin = 90, ymax = 100, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 20, y = 95, label = paste('Search (n=',
                                                 format_statistics(total_results_from_search),
                                                 ')', sep = ''), size = font_size)

p <- p +
  geom_segment(
    x = 20, xend = 20, y = 90, yend = 87.5,
    size = 0.15) +
  geom_segment(
    x = 45, xend = 45, y = 90, yend = 87.5,
    size = 0.15) +
  geom_segment(
    x = 70, xend = 70, y = 90, yend = 87.5,
    size = 0.15) +
  geom_segment(
    x = 95, xend = 95, y = 90, yend = 87.5,
    size = 0.15) +
  geom_segment(
    x = 20, xend = 95, y = 87.5, yend = 87.5,
    size = 0.15) +
  geom_segment(
    x = 35, xend = 35, y = 87.5, yend = 85,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed"))

# p <- p +
#   geom_rect(xmin = 12, xmax = 52, ymin = 80, ymax = 85, color = 'black',
#             fill = 'white', size = 0.25) +
#   annotate('text', x = 28, y = 82.5, label = paste('Total results from search (n=',
#                                                    format_statistics(total_results_from_search),
#                                                    ')', sep = ""), size = font_size)

p <- p +
  geom_segment(
    x = 35, xend = 55, y = 77.5, yend = 77.5,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed")) +
  geom_segment(
    x = 35, xend = 35, y = 80, yend = 75,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed"))

p <- p +
  geom_rect(xmin = 55, xmax = 101, ymin = 75, ymax = 80, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 57, y = 77.5, label = paste('Duplicates removed (n=',
                                                   format_statistics(duplicates_removed),
                                                   ')', sep = ""), size = font_size, hjust = 0)

p <- p +
  geom_rect(xmin = 12, xmax = 52, ymin = 70, ymax = 75, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 25, y = 72.5, label = paste('Records screened (n=',
                                                   format_statistics(records_screened),
                                                   ')', sep = ""), size = font_size)

p <- p +
  geom_segment(
    x = 35, xend = 55, y = 67.5, yend = 67.5,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed")) +
  geom_segment(
    x = 35, xend = 35, y = 70, yend = 65,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed"))

p <- p +
  geom_rect(xmin = 55, xmax = 101, ymin = 70, ymax = 65, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 57, y = 67.5, label = paste('datas excluded (Title/Abstract) (n=',
                                                   format_statistics(exclusion1),
                                                   ')', sep = ""), size = font_size, hjust = 0)

p <- p +
  geom_rect(xmin = 12, xmax = 52, ymin = 60, ymax = 65, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 28, y = 62.5, label = paste('Full-text datas retrieved (n=',
                                                   format_statistics(full_text_articles_retrieved),
                                                   ')', sep = ""), size = font_size)


p <- p +
  geom_segment(
    x = 35, xend = 55, y = 57.5, yend = 57.5,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed")) +
  geom_segment(
    x = 35, xend = 35, y = 60, yend = 40.5,
    size = 0.15, lineend = "butt",
    arrow = arrow(length = unit(1, "mm"), type = "closed"))

p <- p +
  geom_rect(xmin = 55, xmax = 101, ymin = 62.5, ymax = 35.5, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 57, y = 60, label = paste('Papers excluded (Full-text) (total: n=',
                                                 format_statistics(exclusion2),
                                                 ')', sep = ""), size = font_size, hjust = 0)
#   annotate('text', x = 57, y = 56, label = paste('- Inclusion criterion 1: DESCRIPTION (n=',
#                                                  format_statistics(inclusion_2_criterion1),
#                                                  ')', sep = ""), size = font_size, hjust = 0) +
#   annotate('text', x = 57, y = 53, label = paste('- Inclusion criterion 2: DESCRIPTION (n=',
#                                                  format_statistics(inclusion_2_criterion2),
#                                                  ')', sep = ""), size = font_size, hjust = 0)


# p <- p +
#   geom_rect(xmin = 18, xmax = 52, ymin = 25, ymax = 35, color = 'black',
#             fill = 'white', size = 0.25) +
#   annotate('text', x = 36, y = 30, label = paste('Articles included in the synthesis\n (n=',
#                                                  format_statistics(articles_indluded_in_synthesis),
#                                                  ')', sep = ""), size = font_size)

# p <- p +
#   geom_segment(
#     x = 35, xend = 35, y = 25, yend = 20,
#     size = 0.15, lineend = "butt",
#     arrow = arrow(length = unit(1, "mm"), type = "closed"))

p <- p +
  geom_rect(xmin = 12, xmax = 52, ymin = 35.5, ymax = 40.5, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 30, y = 38, label = paste('datas included in the synthesis (n=',
                                                 format_statistics(articles_indluded_in_synthesis),
                                                 ')', sep = ""), size = font_size)

p <- p +  theme_void() + theme(plot.margin = margin(-0.5, 0, -4, -0.6, "cm"))

# devEMF::emf('output/prisma.emf', width = 10, height = 6)
# jpeg('output/prisma.jpg', width = 1000, height = 600)
# tikzDevice::tikz('output/prisma.tex', width=6.3, height=3.5, timestamp = FALSE)
pdf('output/prisma.pdf', width=10, heigh=6)
plot(p)
dev.off()
