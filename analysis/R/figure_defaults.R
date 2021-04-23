#suppressMessages(extrafont::loadfonts(device="win"))
suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(grid))
suppressPackageStartupMessages(library(dplyr))

custom_font = 'Helvetica'
font_size <- 9

general_theme = theme_bw() + theme(plot.title = element_text(size = font_size, family = custom_font, margin = margin(b = 0.1, unit = "cm")),
                                   axis.title = element_text(size = font_size*0.93, family = custom_font, vjust=-1),
                                   axis.title.y = element_text(size = font_size*0.93),
                                   axis.text.x = element_text(size = font_size*0.93, family = custom_font,colour="black", margin = margin(3,3,3,3,"pt")),
                                   axis.text.y = element_text(size = font_size*0.93, colour = "black", family = custom_font, margin = margin(3,3,3,3,"pt")),
                                   panel.grid.major = element_line(colour = "grey30", size = 0.4),
                                   panel.border = element_rect(linetype = 'solid', colour = "black", size = 1.1),
                                   legend.text = element_blank())
