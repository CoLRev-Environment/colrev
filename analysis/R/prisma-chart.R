# https://mran.revolutionanalytics.com/web/packages/PRISMAstatement/vignettes/PRISMA.html

# based on https://rpubs.com/phiggins/461686
suppressPackageStartupMessages(library(tidyverse))

source('analyses/load_data.R')

font_size = 3

search_db_google_scholar <- nrow(paper[paper$search.db.google.scholar,])
search_db_ais_library <- nrow(paper[paper$search.db.ais.library,])
search_toc <- nrow(paper[paper$search.toc,])
search_complementary <- nrow(paper[paper$search.complementary,])

total_results_from_search = sum(search_db_google_scholar, search_db_ais_library, search_toc, search_complementary)

records_screened = nrow(paper)
duplicates_removed = total_results_from_search - records_screened

exclusion1 = nrow(paper[!paper$inclusion_1,])
full_text_articles_retrieved = nrow(paper[paper$inclusion_1,])

# in the following, we only need the instances after inclusion 1
paper <- paper[!is.na(paper$inclusion_2),]

exclusion2 = nrow(paper[!paper$inclusion_2,])
inclusion_2_criterion1 = nrow(paper[!paper$inclusion_2_criterion1,])
inclusion_2_criterion2 = nrow(paper[!paper$inclusion_2_criterion2,])

articles_indluded_in_synthesis = nrow(paper[paper$inclusion_2,])

extraction = nrow(paper[paper$data_extraction & paper$inclusion_2,]) # nrow(paper[paper$Extraction == 'yes',])

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
  annotate('text', x = 20, y = 95, label = paste('Table-of-content scan\n (n=',
                                                  format_statistics(search_toc),
                                                  ')', sep = ''), size = font_size)

p <- p +
  geom_rect(xmin = 35, xmax =55, ymin = 90, ymax = 100, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 45, y = 95, label = paste('Google Scholar\n (n=',
                                                  format_statistics(search_db_google_scholar),
                                                  ')', sep = ''), size = font_size)

p <- p +
  geom_rect(xmin = 60, xmax =80, ymin = 90, ymax = 100, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 70, y = 95, label = paste('AIS Library\n (n=',
                                                  format_statistics(search_db_ais_library),
                                                  ')', sep = ''), size = font_size)

p <- p +
  geom_rect(xmin = 85, xmax = 103, ymin = 90, ymax = 100, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 94, y = 95, label = paste('Complementary \n search (n=',
                                                  format_statistics(search_complementary),
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

p <- p +
  geom_rect(xmin = 12, xmax = 52, ymin = 80, ymax = 85, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 28, y = 82.5, label = paste('Total results from search (n=',
                                                    format_statistics(total_results_from_search),
                                                    ')', sep = ""), size = font_size)

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
  annotate('text', x = 57, y = 67.5, label = paste('Papers excluded (Title/Abstract) (n=',
                                                    format_statistics(exclusion1),
                                                    ')', sep = ""), size = font_size, hjust = 0)

p <- p +
  geom_rect(xmin = 12, xmax = 52, ymin = 60, ymax = 65, color = 'black',
            fill = 'white', size = 0.25) +
  annotate('text', x = 28, y = 62.5, label = paste('Full-text papers retrieved (n=',
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
                                                  ')', sep = ""), size = font_size, hjust = 0) +
  annotate('text', x = 57, y = 56, label = paste('- Inclusion criterion 1: DESCRIPTION (n=',
                                                  format_statistics(inclusion_2_criterion1),
                                                  ')', sep = ""), size = font_size, hjust = 0) +
  annotate('text', x = 57, y = 53, label = paste('- Inclusion criterion 2: DESCRIPTION (n=',
                                                  format_statistics(inclusion_2_criterion2),
                                                  ')', sep = ""), size = font_size, hjust = 0)


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
  annotate('text', x = 30, y = 38, label = paste('Papers included in the synthesis (n=',
                                                  format_statistics(articles_indluded_in_synthesis),
                                                  ')', sep = ""), size = font_size)

p <- p +  theme_void() + theme(plot.margin = margin(-0.5, 0, -4, -0.6, "cm"))

# devEMF::emf('output/prisma.emf', width = 10, height = 6)
# jpeg('output/prisma.jpg', width = 1000, height = 600)
# tikzDevice::tikz('output/prisma.tex', width=6.3, height=3.5, timestamp = FALSE)
pdf('output/prisma.pdf', width=10, heigh=6)
plot(p)
dev.off()
