source('analyses/load_data.R')
source('analyses/figure_defaults.R')

papers_included_years <- plyr::count(subset(paper, inclusion_2 & YEAR > 2000 & YEAR < 2020), vars = c('YEAR'))

# imputation: show data from 2000 to 2019
for (i in 2000:2019) {
  if (nrow(papers_included_years[papers_included_years$YEAR == i,]) == 0) {
    papers_included_years <- rbind(papers_included_years, data.frame(YEAR = i, freq = 0))
  }
}
papers_included_years$year <- as.numeric(papers_included_years$YEAR)
papers_included_years <- plyr::arrange(papers_included_years, YEAR)
labels_years <- seq(min(papers_included_years$YEAR), max(papers_included_years$YEAR), 1)

labels_nr_lrs <- seq(0,11,1)
papers_included_years2 <- papers_included_years %>%
  select(YEAR, freq) %>%
  do(as.data.frame(spline(x = .[['YEAR']], y = .[['freq']], n = nrow(.)*20)))
papers_timeline <- ggplot(papers_included_years, aes(x = YEAR, y = freq)) +
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
