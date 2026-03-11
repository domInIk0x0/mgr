library(vcfR)
library(progress)
library(rehh)
library(dplyr)
set.seed(123)


calculate_similarity_matrix <- function(hap_matrix, reference = 1, thresholds = c(1, seq(5, 100, by = 5))) {
  ref <- hap_matrix[1, ]
  n_sites <- ncol(hap_matrix)
  n_samples <- nrow(hap_matrix)
  
  result <- matrix(0, nrow = length(thresholds), ncol = n_sites)
  rownames(result) <- paste0(thresholds, "%")
  colnames(result) <- colnames(hap_matrix)
  
  for (i in seq_len(n_sites)) {
    cat('Przetwarzanie dla odległości:', i, '/', n_sites, '\n')
    frag <- hap_matrix[, 1:i, drop = FALSE]
    frag_ref <- ref[1:i]
    
    # % identycznych pozycji dla każdego osobnika
    sim <- apply(frag, 1, function(x) mean(x == frag_ref) * 100)
    
    
    for (t in seq_along(thresholds)) {
      result[t, i] <- sum(sim >= thresholds[t])
    }
  }
  return(result)
}


calculate_weighted_mean <- function(pi_matrix) {
  weights <- as.numeric(gsub("%", "", rownames(pi_matrix)))
  
  if (length(weights) != nrow(pi_matrix)) {
    stop("Liczba wierszy macierzy nie zgadza się z liczbą wag.")
  }
  
  weighted_means <- apply(pi_matrix, 2, function(x) {
    exclusive_counts <- x - c(x[-1], 0)
    
    total_individuals <- sum(exclusive_counts)
    
    if (total_individuals == 0) {
      return(0) 
    }
    
    sum(weights * exclusive_counts) / total_individuals
  })
  
  result <- data.frame(column = colnames(pi_matrix),
                       weighted_mean = weighted_means,
                       row.names = NULL)
  
  return(result)
}


plot_weighted_means <- function(means, x_breaks_step = 1) {
  ggplot(data = means, aes(x = column, y = weighted_mean)) +
    geom_point(size = 0.5, color = "#00884B") +
    geom_line(group = 1, color = "#00884B", linewidth = 1, alpha = 0.6) +
    theme_minimal(base_size = 14) +
    labs(
      title = "Średnie ważone dla kolumn macierzy podobieństwa",
      x = "Pozycja chromosomowa",
      y = "Średnia ważona"
    ) +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1)
    ) +
    scale_x_discrete(
      breaks = means$column[seq(1, length(means$column), by = x_breaks_step)]
    )
}


plot_weighted_means_lr <- function(means_l, means_r, s, x_breaks_step = 1) {
  means_l <- means_l %>%
    mutate(column = factor(column, levels = rev(column)),
           side = "left")
  
  means_r <- means_r %>%
    mutate(column = factor(column, levels = column),
           side = "right")
  
  means_all <- bind_rows(means_l, means_r)
  
  means_all <- means_all %>%
    mutate(pos = as.numeric(sub("^[^:]+:([^:]+):.*$", "\\1", column)))
  
  p <- ggplot(data = means_all, aes(x = pos, y = weighted_mean, color = side, group = side)) +
    geom_point(size = 0.5) +
    geom_line(linewidth = 1, alpha = 0.6) +
    geom_vline(xintercept = s, color = "red", linetype = "dashed", linewidth = 0.8) +
    theme_minimal(base_size = 14) +
    labs(
      title = "Średnie ważone dla kolumn macierzy podobieństwa",
      x = "Pozycja genomowa",
      y = "Średnia ważona"
    ) +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
      legend.position = "none"
    ) +
    scale_color_manual(values = c("left" = "#00884B", "right" = "#00884B"))
  
  return(p)
}

normalize_minmax <- function(x) {
  return((x - min(x)) / (max(x) - min(x)))
}


mrk <- '6:32095725:T:C'  # analogicznie dla wariantu 6:32095725:T:C
s <- as.numeric(strsplit(mrk, ':')[[1]][2])
mb <- 100000

# Ekstrakcja wariantów w prawo i obliczenie % identyczności
hap_matrix_r <- hh@haplo[, which(hh@positions >= s & hh@positions < s + mb)]
variant_ids <- colnames(hap_matrix_r)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_r) <- d_mb

cat('Ilość wariantów na prawo od markera :', length(colnames(hap_matrix_r)), '\n')
identity_matrix_r <- calculate_similarity_matrix(hap_matrix_r, reference = 1)
means_r <- calculate_weighted_mean(identity_matrix_r)
means_r$weighted_mean <- normalize_minmax(means_r$weighted_mean)
identity_matrix_r[15: 21,c(1:8)]

# Ekstrakcja wariantów w lewo i obliczenie % identyczności
hap_matrix_l <- hh@haplo[, which(hh@positions <= s  & hh@positions >= s - mb)]
variant_ids <- colnames(hap_matrix_l)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_l) <- d_mb

ord <- order(as.numeric(names(hap_matrix_l[1, ])), decreasing = T)
hap_matrix_l <- hap_matrix_l[, ord]
cat('Ilość wariantów na lewo od markera :', length(colnames(hap_matrix_l)), '\n')

identity_matrix_l <- calculate_similarity_matrix(hap_matrix_l, reference = 1)
means_l <- calculate_weighted_mean(identity_matrix_l[15:21, ])
means_l$weighted_mean <- normalize_minmax(means_l$weighted_mean)

# Wykresy rozpadu
plot_weighted_means(means_l, x_breaks_step = 150)
plot_weighted_means(means_r, x_breaks_step = 150)
plot_weighted_means_lr(means_l = means_l, means_r = means_r, s = s/1000000,x_breaks_step = 15)
