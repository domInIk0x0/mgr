library(vcfR)
library(progress)
library(rehh)
library(dplyr)
set.seed(123)

calculate_similarity_matrix <- function(hap_matrix, thresholds = c(1, seq(5, 100, by = 5))) {
  n_sites <- ncol(hap_matrix)
  
  group_0 <- hap_matrix[hap_matrix[, 1] == 0, , drop = FALSE]
  group_1 <- hap_matrix[hap_matrix[, 1] == 1, , drop = FALSE]
  
  get_majority <- function(v) {
    if (length(v) == 0) return(NA)
    as.numeric(names(which.max(table(v))))
  }
  
  ref_0 <- apply(group_0, 2, get_majority)
  ref_0[1] <- 0 
  
  ref_1 <- apply(group_1, 2, get_majority)
  ref_1[1] <- 1 
  
  result_0 <- matrix(0, nrow = length(thresholds), ncol = n_sites)
  rownames(result_0) <- paste0(thresholds, "%")
  colnames(result_0) <- colnames(hap_matrix)
  
  result_1 <- matrix(0, nrow = length(thresholds), ncol = n_sites)
  rownames(result_1) <- paste0(thresholds, "%")
  colnames(result_1) <- colnames(hap_matrix)
  
  for (i in seq_len(n_sites)) {
    cat('Przetwarzanie dla odległości:', i, '/', n_sites, '\r') 
    
    if (nrow(group_0) > 0) {
      frag_0 <- group_0[, 1:i, drop = FALSE]
      frag_ref_0 <- ref_0[1:i]
      
      sim_0 <- rowMeans(sweep(frag_0, 2, frag_ref_0, "==")) * 100
      
      for (t in seq_along(thresholds)) {
        result_0[t, i] <- sum(sim_0 >= thresholds[t])
      }
    }
    
    if (nrow(group_1) > 0) {
      frag_1 <- group_1[, 1:i, drop = FALSE]
      frag_ref_1 <- ref_1[1:i]
      
      sim_1 <- rowMeans(sweep(frag_1, 2, frag_ref_1, "==")) * 100
      
      for (t in seq_along(thresholds)) {
        result_1[t, i] <- sum(sim_1 >= thresholds[t])
      }
    }
  }
  cat('\nZakończono.\n')
  
  return(list(ref_0_matrix = result_0, ref_1_matrix = result_1))
}


calculate_weighted_mean <- function(pi_matrix_0, pi_matrix_1) {
  process_matrix <- function(pi_matrix) {
    if (is.null(pi_matrix) || nrow(pi_matrix) == 0) return(NULL)
    
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
    
    min_val <- min(weighted_means, na.rm = TRUE)
    max_val <- max(weighted_means, na.rm = TRUE)
    
    if (max_val > min_val) {
      weighted_means_norm <- (weighted_means - min_val) / (max_val - min_val)
    } else {
      weighted_means_norm <- rep(0, length(weighted_means))
    }
    
    result <- data.frame(column = colnames(pi_matrix),
                         weighted_mean = weighted_means,
                         weighted_mean_norm = weighted_means_norm,
                         row.names = NULL)
    return(result)
  }
  
  result_0 <- process_matrix(pi_matrix_0)
  result_1 <- process_matrix(pi_matrix_1)
  
  return(list(weighted_mean_0 = result_0, 
              weighted_mean_1 = result_1))
}


plot_weighted_means_lr <- function(means_l_0, means_l_1, means_r_0, means_r_1, s) {
  
  means_l_0 <- means_l_0 %>% mutate(column = factor(column, levels = rev(column)), side = "left", ref = "Ref 0")
  means_r_0 <- means_r_0 %>% mutate(column = factor(column, levels = column), side = "right", ref = "Ref 0")
  means_l_1 <- means_l_1 %>% mutate(column = factor(column, levels = rev(column)), side = "left", ref = "Ref 1")
  means_r_1 <- means_r_1 %>% mutate(column = factor(column, levels = column), side = "right", ref = "Ref 1")
  
  means_all <- bind_rows(means_l_0, means_r_0, means_l_1, means_r_1)
  means_all <- means_all %>% mutate(pos = as.numeric(sub("^[^:]+:([^:]+):.*$", "\\1", column)))
  
  p <- ggplot(data = means_all, aes(x = pos, y = weighted_mean, color = ref, group = interaction(side, ref))) +
    geom_point(size = 0.5) +
    geom_line(linewidth = 1, alpha = 0.6) +
    geom_vline(xintercept = s, color = "black", linetype = "dashed", linewidth = 0.8) +
    theme_minimal(base_size = 14) +
    labs(
      title = "Średnia ważona podobieństwa (w %)",
      x = "Pozycja genomowa",
      y = "Średnia ważona (%)",
      color = "Grupa"
    ) +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
      legend.position = "bottom"
    ) +
    scale_color_manual(values = c("Ref 0" = "#0072B2", "Ref 1" = "#D55E00"))
  
  return(p)
}

normalize_minmax <- function(x) {
  return((x - min(x)) / (max(x) - min(x)))
}

# Marker startowy
mrk <- '6:32095725:T:C'  
s <- as.numeric(strsplit(mrk, ':')[[1]][2])
mb <- 250000

# Ekstrakcja wariantów w prawo i obliczenie % identyczności
hap_matrix_r <- hh@haplo[, which(hh@positions >= s & hh@positions < s + mb)]
variant_ids <- colnames(hap_matrix_r)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_r) <- d_mb

cat('Ilość wariantów na prawo od markera :', length(colnames(hap_matrix_r)), '\n')
identity_matrix_r <- calculate_similarity_matrix(hap_matrix_r)
means_r <- calculate_weighted_mean(identity_matrix_r$ref_0_matrix, identity_matrix_r$ref_1_matrix)
print(identity_matrix_r$ref_0_matrix[15:21,1:8])

# Ekstrakcja wariantów w lewo i obliczenie % identyczności
hap_matrix_l <- hh@haplo[, which(hh@positions <= s  & hh@positions >= s - mb)]
variant_ids <- colnames(hap_matrix_l)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_l) <- d_mb

ord <- order(as.numeric(names(hap_matrix_l[1, ])), decreasing = T)
hap_matrix_l <- hap_matrix_l[, ord]
cat('Ilość wariantów na lewo od markera :', length(colnames(hap_matrix_l)), '\n')

identity_matrix_l <- calculate_similarity_matrix(hap_matrix_l)
means_l <- calculate_weighted_mean(identity_matrix_l$ref_0_matrix, identity_matrix_l$ref_1_matrix)

# Wykres rozpadu
plot_weighted_means_lr(means_l_0 = means_l$weighted_mean_0 , means_l_1 =  means_l$weighted_mean_1 , 
                       means_r_0 = means_r$weighted_mean_0 , means_r_1 = means_r$weighted_mean_1, 
                       s = s / 1000000)
