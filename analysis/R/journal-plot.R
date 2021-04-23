source('analyses/load_data.R')
source('analyses/figure_defaults.R')

paper_freq <- plyr::count(subset(paper, inclusion_2), vars = c("JOURNAL"))
# paper_freq <- subset(paper_freq, paper_freq$freq > 10)
paper_freq <- paper_freq[order(paper_freq$freq),]
paper_freq$JOURNAL <- as.character(paper_freq$JOURNAL)
paper_freq$JOURNAL <- ordered(paper_freq$JOURNAL, levels = paper_freq$JOURNAL)
paper_freq$freq <- as.numeric(paper_freq$freq)

journal_plot <- ggplot(paper_freq, aes(x = JOURNAL, y = freq)) +
  geom_bar(stat = "identity", width = .70, fill = "grey25") +
  # geom_text(aes(x = JOURNAL, y = freq + 2, label = freq), size = 0.32*font_size, family = custom_font) +
  scale_y_continuous(breaks = c(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14),
                     labels = c(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14),
                     expand = c(0, 0),
                     limits = c(0,14)) +
  xlab("") + ylab("Number of Papers") +
  coord_flip() +
  general_theme + theme(plot.margin = unit(c(0.1,0.1,0.1,-0.4),"cm"),
                        panel.grid.major = element_line(colour = "grey70"),
                        axis.ticks = element_line(colour = "black", size = 1, linetype = "solid"),
                        axis.ticks.length = unit(0.13, "cm"),
                        axis.ticks.y = element_blank(),
                        axis.text.y = element_text(face = "italic"))

pdf('output/journals.pdf', width=6, heigh=2)
# tikzDevice::tikz('output/journals.tex', width=6.3, height=1.9, timestamp = FALSE)
plot(journal_plot)
dev.off()
