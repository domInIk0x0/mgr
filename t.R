library(vcfR)
library(progress)
library(rehh)

#### Usuwanie duplikatow w pliku vcf ####
vcf <- read.vcfR("/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/c19_f.vcf.gz")
df <- as.data.frame(vcf@fix)
unique_idx <- !duplicated(paste0(df$CHROM, "_", df$POS))
vcf_unique <- vcf[unique_idx, ]
write.vcf(vcf_unique, file = "/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/c19_f_test.vcf.gz")


#### Tworzenie macierzy haplotypow ####
hh <- data2haplohh(hap_file = '/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/c19_f_test.vcf.gz',
                   vcf_reader = "vcfR",
                   chr.name = 19, polarize_vcf=FALSE,
                   allele_coding = "01",
                   )

hh@haplo[1:10, 1:5]


#### Funkcje do mierzenia spadku identycznosci ####
create_haplo_dict <- function(hh_matrix, haplo_len, distrib_table, n_samples) {
  haplo_dict <- list()
  
  for (index in 1:length(distrib_table)){
    haplo <- names(distrib_table[index])
    splitted_haplo <- strsplit(haplo, '')[[1]]
    
    n_haplo <- distrib_table[[index]]
    
    for (l in 1:haplo_len){
      label <- paste0('pos_', l)
      
      if (splitted_haplo[l] == '0'){
        if ((is.null(haplo_dict[[label]]['0'])) || (is.na(haplo_dict[[label]]['0']))){
          haplo_dict[[label]]['0'] <- n_haplo
        }
        else{
          haplo_dict[[label]]['0'] <- haplo_dict[[label]]['0'] + n_haplo
        }
      }
      else{
        if (is.na(haplo_dict[[label]]['1']) || (is.null(haplo_dict[[label]]['1']))){
          haplo_dict[[label]]['1'] <- n_haplo
        }
        else{
          haplo_dict[[label]]['1'] <- haplo_dict[[label]]['1'] + n_haplo
        }
      }
    }
  }
  return(haplo_dict)
}

calculate_pi <- function(hh_matrix, haplo_len){
  hh_matrix <- apply(hh_matrix[, 1:haplo_len], 1, function(x) paste0(x, collapse = ""))
  distrib_table <- table(hh_matrix)
  n_samples <- sum(distrib_table)
  
  haplo_dict <- create_haplo_dict(hh_matrix = hh_matrix,
                                  haplo_len = haplo_len,
                                  distrib_table = distrib_table, 
                                  n_samples = n_samples)
  
  all_pi <- data.frame()
  for (val in names(distrib_table)){
    splitted_haplo <- strsplit(val, '')[[1]]

    s <- 0
    for (z in 1:haplo_len){
      pos <- paste0('pos_', z)
      a <- splitted_haplo[[z]]
      n <- haplo_dict[[pos]][splitted_haplo[z]]
      s <- s + n
    }
    pi <- s /(n_samples * haplo_len)
    all_pi[1, val] <- pi
  }
  return(all_pi)
}


calculate_table <- function(hap_matrix, for_n_len = 3) {
  new_hap_matrix <- as.data.frame(matrix(0, nrow = nrow(hap_matrix), ncol = for_n_len))
  rownames(new_hap_matrix) <- rownames(hap_matrix)
  colnames(new_hap_matrix) <- colnames(hap_matrix)[1:for_n_len]
  
  t <- table(hap_matrix[, 1])
  freq0 <- t["0"] / sum(t)
  freq1 <- t["1"] / sum(t)
  
  new_hap_matrix[hap_matrix[, 1] == 0, 1] <- freq0
  new_hap_matrix[hap_matrix[, 1] == 1, 1] <- freq1
  
  for (i in 2:for_n_len) {
    cat('Przetwarzanie dla odległości:', i, '/', for_n_len, '\n')
    all_pi <- calculate_pi(hap_matrix, i)
    pi_cols <- colnames(all_pi)
    
    seq_for_rows <- apply(hap_matrix[, 1:i, drop = FALSE], 1, paste0, collapse = "")
    
    for (row_idx in seq_along(seq_for_rows)) {
      seq_name <- seq_for_rows[row_idx]
      if (seq_name %in% pi_cols) {
        new_hap_matrix[row_idx, i] <- as.numeric(all_pi[1, seq_name])
      }
    }
  }
  
  return(new_hap_matrix)
}


# Druga wersja
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
    stop("Liczba wierszy macierzy nie zgadza się z liczbą wag (procentów).")
  }
  
  weighted_means <- apply(pi_matrix, 2, function(x) {
    sum(weights * x) / sum(x)
  })
  
  result <- data.frame(column = colnames(pi_matrix),
                       weighted_mean = weighted_means,
                       row.names = NULL)
  
  return(result)
}

# zeby uzywac ramka z dwoma kolumnami x = column, y = weighted_mean 
# gdzie column to etykieta kolumny czyli odleglosc markera
plot_weighted_means <- function(means, x_breaks_step = 1) {
  ggplot(data = means, aes(x = column, y = weighted_mean)) +
    geom_point(size = 0.5, color = "#2E86AB") +
    geom_line(group = 1, color = "#2E86AB", linewidth = 1, alpha = 0.6) +
    theme_minimal(base_size = 14) +
    labs(
      title = "Średnie ważone dla kolumn",
      x = "Kolumna",
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
      title = "Średnie ważone dla kolumn",
      x = "Pozycja genomowa",
      y = "Średnia ważona"
    ) +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
      legend.position = "none"
    ) +
    scale_color_manual(values = c("left" = "#2E86AB", "right" = "#2E86AB"))
  
  return(p)
}




#### Wybranie markera startowego ####
# 40650504 + 400000
mrk <- names(hh@positions[100000])
mrk <- '19:24496326:G:A'
s <- as.numeric(strsplit(mrk, ':')[[1]][2])
mb <- 1000000

#### Obliczanie wynikow ####
# Zamiana nazw kolumn na odleglosci od markera startowego
hap_matrix_r <- hh@haplo[, which(hh@positions >= s & hh@positions < s + mb)]
variant_ids <- colnames(hap_matrix_r)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_r) <- d_mb

cat('Ilość wariantów na prawo od markera :', length(colnames(hap_matrix_r)), '\n')

# Obliczenie macierzy 
identity_matrix_r <- calculate_similarity_matrix(hap_matrix_r, reference = 1)

View(identity_matrix_r[16:21,])
means_r <- calculate_weighted_mean(identity_matrix_r)

View(identity_matrix_r)

hap_matrix_l <- hh@haplo[, which(hh@positions <= s  & hh@positions >= s - mb)]
variant_ids <- colnames(hap_matrix_l)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_l) <- d_mb

ord <- order(as.numeric(names(hap_matrix_l[1, ])), decreasing = T)
hap_matrix_l <- hap_matrix_l[, ord]
cat('Ilość wariantów na lewo od markera :', length(colnames(hap_matrix_l)), '\n')

identity_matrix_l <- calculate_similarity_matrix(hap_matrix_l, reference = 1)
means_l <- calculate_weighted_mean(identity_matrix_l)
View(identity_matrix_l[19:21, ])
View(means_l)

plot_weighted_means(means_l, x_breaks_step = 150)
plot_weighted_means(means_r, x_breaks_step = 150)
plot_weighted_means_lr(means_l = means_l, means_r = means_r, s = s/1000000,x_breaks_step = 15)
plot(calc_ehhs(hh, mrk = mrk))
# dane symulowane sim1000 g


#### h_p entropia ####
H_p <- function(hh_matrix, n_threads = 2) {
  n_v <- ncol(hh_matrix)
  n_samples <- nrow(hh_matrix)
  
  hh_char <- apply(hh_matrix, 2, as.character)
  
  compute_entropy <- function(len) {
    hh_sub <- do.call(paste0, as.data.frame(hh_char[, 1:len, drop = FALSE]))
    pi <- table(hh_sub) / n_samples
    entropy <- -sum(pi * log(pi))
    cat('Liczenie dla dlugosci:', len, '/', n_v, '\n')
    return(entropy)
  }
  entropy_vec <- mclapply(1:n_v, compute_entropy, mc.cores = n_threads)
  data.frame(len = 1:n_v, entropy = unlist(entropy_vec))
}
ncol(hap_matrix_l)
h_p_r <- H_p(hap_matrix_r)
h_p_l <- H_p(hap_matrix_l)

h_p_r$x_pos <- 0:(nrow(h_p_r)-1)
h_p_l$x_pos <- 0:-(nrow(h_p_l)-1)

h_p_r$hap <- "R"
h_p_l$hap <- "L"

df_plot <- rbind(h_p_r, h_p_l)

ggplot(df_plot, aes(x = x_pos, y = entropy, color = hap)) +
  geom_line(size = 1) +
  geom_point() +
  scale_x_continuous(name = "Odległość od środka") +
  scale_y_continuous(name = "Entropia") +
  theme_minimal() +
  ggtitle("E od markera s") +
  theme(plot.title = element_text(hjust = 0.5))


plot(calc_ehhs(hh, mrk=mrk))
scan <- scan_hh(hh, threads = 28)
View(scan)


test <- hap_matrix_r[,1:100]
tb <- calculate_table(test, for_n_len = 100)
View(tb)

hist(tb[, 100])
plot(tb[,1:10])
calculate_weighted_mean(tb)
plot(apply(tb, 2, function(x) mean(x)))


#### Macierz haplotypow jako obraz ####
mrk <- "19:40650504:G:A"
idx <- which(colnames(hh@haplo) == mrk)
start <- max(1, idx - 600)  
end   <- min(ncol(hh@haplo), idx + 600) 
hh_sub <- hh@haplo[, start:end]

h <- hh_sub
h <- as.matrix(hap_matrix[1:512, 1:512])
h <- h[nrow(h):1, ]
image(1:ncol(h), 1:nrow(h), t(h),
      col=c("black", "white"), axes=FALSE, xlab="", ylab="")
axis(1, at=1:ncol(h), labels=colnames(h))
axis(2, at=1:nrow(h), labels=rownames(h))



# kilka obrazow
h_full <- as.matrix(hap_matrix)
rysuj_obraz <- function(h) {
  h <- h[nrow(h):1, ]  
  image(1:ncol(h), 1:nrow(h), t(h),
        col=c("black", "white"), axes=FALSE, xlab="", ylab="")
}

par(mfrow = c(4, 4), mar = c(0.5, 0.5, 0.5, 0.5))
sizes <- c(16, 32, 64, 112, 160, 200, 256, 320, 384, 448, 480, 512, 600, 700, 800, 900)

for (s in sizes) {
  s <- min(s, nrow(h_full), ncol(h_full))
  h <- h_full[1:s, 1:s]
  rysuj_obraz(h)
}
par(mfrow = c(1,1))


#### srednie srednich ####

t <- hap_matrix[, 1:3] 
df <- data.frame(id = rownames(t), matrix(0, nrow = nrow(t), ncol = ncol(t)))

for (s in 1:nrow(t)){ 
  cat('Probka nr:', s, '/', nrow(t), '\n')
  ref <- t[s, ]
  for(m in 1:ncol(t)){
    avg <- mean(apply(ref[1:m] == t[, 1:m, drop = FALSE], 1, mean))
    df[s, m] <- avg  
  }
}

t <- as.matrix(hap_matrix[, 1:100])
n <- nrow(t)
p <- ncol(t)

df <- data.frame(id = rownames(t), matrix(0, n, p))

for (s in 1:n) {
  cat("Probka nr:", s, "/", n, "\n")
  ref <- t[s, ]
  
  match_mat <- t == matrix(ref, n, p, byrow = TRUE)
  cum_match <- t(apply(match_mat, 1, cumsum))
  avg <- colMeans(cum_match / matrix(1:p, n, p, byrow = TRUE))
  df[s, -1] <- avg
}

View(df)

col_means <- data.frame(mean_value = colMeans(df[, -1]))
ggplot(col_means, aes(x = mean_value)) +
  geom_histogram(binwidth = 0.01, fill = "steelblue", color = "black") +
  theme_minimal() +
  labs(title = "Histogram średnich kolumn", x = "Średnia", y = "Liczba kolumn")

#### Pojawianie sie nowych ciagow haplotypow w zaleznosci od dlguosci ####
t <- hh@haplo[, 1:2000] 
n <- nrow(t)
p <- ncol(t)

t_char <- apply(t, 2, as.character)
num_unique_seq <- integer(p)

seq_mat <- t_char[, 1, drop = FALSE]  # zaczynamy od pierwszej kolumny
num_unique_seq[1] <- length(unique(seq_mat))

for (l in 2:p) {
  cat('Dlugosc:', l, '/', p, '\n')
  seq_mat <- paste0(seq_mat, t_char[, l])
  num_unique_seq[l] <- length(unique(seq_mat))
}

df_len <- data.frame(dl = 1:p, num_of_unique_seq = num_unique_seq)

ggplot(df_len, aes(x = dl, y = num_of_unique_seq)) +
  geom_line(color = "steelblue", size = 1.2) +
  geom_point(color = "red", size = 1) +
  theme_minimal() +
  labs(
    title = "Liczba unikalnych sekwencji vs długość fragmentu haplotypu",
    x = "Długość sekwencji",
    y = "Liczba unikalnych sekwencji"
  )




#### sim1000g ####
library(sim1000G)
library(rehh)
library(gplo)
library(haplsim)
library(HaploSim)
library(rehh)

vcf_file <- "/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/c19_f_test.vcf.gz"

40650504 + 400000

hh@positions[10000]

vcf_s <- readVCF(
  vcf_file, 
  region_start = 5148383, 
  region_end = 5648383, 
  maxNumberOfVariants = 2100,
  min_maf = 0.001
)

View(vcf_s$gt1)
SIM$  
SIM$reset()
?startSimulation()
startSimulation(vcf_s, totalNumberOfIndividuals = 1032)
generateUnrelatedIndividuals(1032)

n_individuals <- nrow(SIM$gt1)   
n_variants <- ncol(SIM$gt1)     


genotypes_01 <- SIM$gt1 + SIM$gt2
genotypes_vcf <- matrix(NA, nrow = n_variants, ncol = n_individuals)

for (i in 1:n_variants) {
  for (j in 1:n_individuals) {
    x <- genotypes_01[j, i]
    if (x == 0) {
      genotypes_vcf[i, j] <- "0|0"
    } else if (x == 1) {
      genotypes_vcf[i, j] <- "0|1"
    } else if (x == 2) {
      genotypes_vcf[i, j] <- "1|1"
    }
  }
}

colnames(genotypes_vcf) <- paste0("ind", 1:n_individuals)

vcf_df <- data.frame(
  CHROM = SIM$varinfo$`#CHROM`,
  POS   = SIM$varinfo$POS,
  ID    = SIM$varinfo$ID,
  REF   = SIM$varinfo$REF,
  ALT   = SIM$varinfo$ALT,
  QUAL  = ".",
  FILTER = "PASS",
  INFO = ".",
  FORMAT = "GT"
)

vcf_df <- cbind(vcf_df, genotypes_vcf)

header_lines <- c(
  "##fileformat=VCFv4.2",
  "##source=SIM_auto",
  paste("#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO", "FORMAT", 
        paste0("ind", 1:n_individuals, collapse="\t"), sep="\t")
)

output_file <- "simulated_data.vcf"
writeLines(header_lines, con = output_file)
write.table(vcf_df, file = output_file, append = TRUE, 
            quote = FALSE, sep = "\t", row.names = FALSE, col.names = FALSE)

hh_sim <- data2haplohh(
  hap_file = output_file,
  vcf_reader = "vcfR",
  chr.name = 19,
  polarize_vcf = FALSE,
  allele_coding = "01"
)

View(hh_sim@haplo)


# na wysymulowanych danych
mrk <- names(hh_sim@positions[600])
s <- as.numeric(strsplit(mrk, ':')[[1]][2])
mb <- 1000000000


hap_matrix_r <- hh_sim@haplo[, which(hh_sim@positions >= s & hh_sim@positions < s + mb)]
variant_ids <- colnames(hap_matrix_r)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_r) <- d_mb

cat('Ilość wariantów na prawo od markera :', length(colnames(hap_matrix_r)), '\n')

identity_matrix_r <- calculate_similarity_matrix(hap_matrix_r, reference = 1)
means_r <- calculate_weighted_mean(identity_matrix_r)


hap_matrix_l <- hh_sim@haplo[, which(hh_sim@positions <= s  & hh_sim@positions >= s - mb)]
variant_ids <- colnames(hap_matrix_l)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_l) <- d_mb

ord <- order(as.numeric(names(hap_matrix_l[1, ])), decreasing = T)
hap_matrix_l <- hap_matrix_l[, ord]
cat('Ilość wariantów na lewo od markera :', length(colnames(hap_matrix_l)), '\n')

identity_matrix_l <- calculate_similarity_matrix(hap_matrix_l, reference = 1)
means_l <- calculate_weighted_mean(identity_matrix_l)

plot_weighted_means(means_l, x_breaks_step = 150)
plot_weighted_means(means_r, x_breaks_step = 150)
plot_weighted_means_lr(means_l = means_l, means_r = means_r, s = s/1000000,x_breaks_step = 15)
plot(calc_ehhs(hh_sim, mrk = mrk))


library(parallel)
H_p()
h_p_r <- H_p(hap_matrix_r)
h_p_l <- H_p(hap_matrix_l)

h_p_r$x_pos <- 0:(nrow(h_p_r)-1)
h_p_l$x_pos <- 0:-(nrow(h_p_l)-1)

h_p_r$hap <- "R"
h_p_l$hap <- "L"

df_plot <- rbind(h_p_r, h_p_l)

ggplot(df_plot, aes(x = x_pos, y = entropy, color = hap)) +
  geom_line(size = 1) +
  geom_point() +
  scale_x_continuous(name = "Odległość od środka") +
  scale_y_continuous(name = "Entropia") +
  theme_minimal() +
  ggtitle("E od markera s") +
  theme(plot.title = element_text(hjust = 0.5))




t <- hh_sim@haplo[, 1:2000] 
n <- nrow(t)
p <- ncol(t)

t_char <- apply(t, 2, as.character)
num_unique_seq <- integer(p)

seq_mat <- t_char[, 1, drop = FALSE]  # zaczynamy od pierwszej kolumny
num_unique_seq[1] <- length(unique(seq_mat))

for (l in 2:p) {
  cat('Dlugosc:', l, '/', p, '\n')
  seq_mat <- paste0(seq_mat, t_char[, l])
  num_unique_seq[l] <- length(unique(seq_mat))
}

df_len <- data.frame(dl = 1:p, num_of_unique_seq = num_unique_seq)

ggplot(df_len, aes(x = dl, y = num_of_unique_seq)) +
  geom_line(color = "steelblue", size = 1.2) +
  geom_point(color = "red", size = 1) +
  theme_minimal() +
  labs(
    title = "Liczba unikalnych sekwencji vs długość fragmentu haplotypu",
    x = "Długość sekwencji",
    y = "Liczba unikalnych sekwencji"
  )






#### Symulacja podobnych próbek do testu macierzy ####
library(SeqArray)
library(GENESIS)
library(SNPRelate)
library(pheatmap)

# Konwersja vcf do gdsa
out_dir <- "/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/gdsy"
vcf_file <- "/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/c19_f_test.vcf.gz"

gds_path <- file.path(out_dir, "c19_imputed.gds")
seqVCF2GDS(vcf.fn = vcf_file,
           out.fn = gds_path,
           storage.option = "LZMA_RA",  
           parallel = TRUE)

gds <- seqOpen(gds_path)

# Ibs do znalezienia podobnych próbek w klastrze
ibs <- snpgdsIBS(gds, num.thread = 28)

ibs.dist <- 1 - ibs$ibs
hc <- hclust(as.dist(ibs.dist), method = "average")
plot(hc, labels = ibs$sample.id, main = "Hierarchical clustering (IBS)", xlab = "", sub = "")

pheatmap(ibs$ibs,
         labels_row = ibs$sample.id,
         labels_col = ibs$sample.id,
         clustering_method = "average",
         main = "IBS similarity heatmap")


# mds
ibs.pca <- cmdscale(as.dist(1 - ibs$ibs), k = 2)
km <- kmeans(ibs.pca, centers = 5)
plot(ibs.pca[,1], ibs.pca[,2],
     col = km$cluster,
     pch = 19,
     xlab = "PC1", ylab = "PC2",
     main = "IBS MDS k-means")
text(ibs.pca[,1], ibs.pca[,2], labels = ibs$sample.id, pos = 3, cex = 0.7)


# bazujac na progu w ibs
threshold <- 0.9
high_sim <- which(ibs$ibs > threshold, arr.ind = TRUE)
high_sim <- high_sim[high_sim[,1] < high_sim[,2], ]

pairs <- data.frame(
  sample1 = ibs$sample.id[high_sim[,1]],
  sample2 = ibs$sample.id[high_sim[,2]],
  ibs_value = ibs$ibs[high_sim]
)
unique_samples <- unique(c(pairs[,1], pairs[,2]))
length(unique_samples)


# klasyczne PCA na macierzy IBS
pca <- prcomp(ibs$ibs, scale. = TRUE)
var_explained <- (pca$sdev^2) / sum(pca$sdev^2)
plot(var_explained,
     type = "b",
     pch = 19,
     xlab = "Principal Component",
     ylab = "Explained Variance",
     main = "PCA - Explained Variance")

plot(pca$x[, 1], pca$x[, 2])


# Ładowanie vcf
vcf_file <- "/mnt/ip114/DominikPietrzak/MASTERD_IHS_HAPLO/PLIKI_PER_CHROM/c19_f_test.vcf.gz"

vcf_ibsvcf_s <- readVCF(
  vcf_file, 
  region_start = 5148383, 
  region_end = 5648383, 
  maxNumberOfVariants = 2100,
  min_maf = 0.001
)

vcf_s$vcf[1:3, ]
gt1 <- vcf_s$gt1
gt2 <- vcf_s$gt2

# funkcja do generowania 
generate_gt <- function(gtn, unique_samples, number_of_draws = 300){
  gt <- as.data.frame(gtn[, unique_samples])
  
  gt$mean <- rowMeans(gt)
  gt$p <- gt$mean / sum(gt$mean)
  
  geno_df <- data.frame(i=1:nrow(gt))
  
  for (i in 1:number_of_draws){
    samples_idx <- sample(1:length(gt$p), size = 300, replace = TRUE, prob = gt$p)
    samples <- gt$p[samples_idx]
    counts <- table(samples)
    
    gt$p_c <- ifelse(gt$p, yes = counts, no = 0)
    
    random_treshold <- sample(2:7, 1)
    gt$hap <- ifelse(gt$p_c >= random_treshold, yes = 1, no = 0) 
    
    s <- paste0('sample', i)
    
    geno_df[, i] <- gt$hap
    colnames(geno_df)[i] <- s
  }
  return(geno_df)
}

generated_gt1 <- generate_gt(gt1, unique_samples, number_of_draws = 300)
generated_gt2 <- generate_gt(gt2, unique_samples, number_of_draws = 300)

heatmap(cor(generated_gt1))
heatmap(cor(generated_gt2))


# dopisanie wygenerowanych probek plus id
new_samples <- colnames(generated_gt1)
vcf_s$individual_ids <- c(vcf_s$individual_ids, new_samples)
vcf_s$gt1 <- cbind(vcf_s$gt1, generated_gt1)
vcf_s$gt2 <- cbind(vcf_s$gt2, generated_gt2)

startSimulation(vcf_s, totalNumberOfIndividuals = ncol(vcf_s$gt1))
generateUnrelatedIndividuals(ncol(vcf_s$gt1))


SIM$gt1[1:3, 1:3]

# Generowanie vcf-a
n_individuals <- nrow(SIM$gt1)   
n_variants <- ncol(SIM$gt1)     

genotypes_01 <- SIM$gt1 + SIM$gt2
genotypes_vcf <- matrix(NA, nrow = n_variants, ncol = n_individuals)

for (i in 1:n_variants) {
  for (j in 1:n_individuals) {
    x <- genotypes_01[j, i]
    if (x == 0) {
      genotypes_vcf[i, j] <- "0|0"
    } else if (x == 1) {
      genotypes_vcf[i, j] <- "0|1"
    } else if (x == 2) {
      genotypes_vcf[i, j] <- "1|1"
    }
  }
}

colnames(genotypes_vcf) <- paste0("ind", 1:n_individuals)

vcf_df <- data.frame(
  CHROM = SIM$varinfo$`#CHROM`,
  POS   = SIM$varinfo$POS,
  ID    = SIM$varinfo$ID,
  REF   = SIM$varinfo$REF,
  ALT   = SIM$varinfo$ALT,
  QUAL  = ".",
  FILTER = "PASS",
  INFO = ".",
  FORMAT = "GT"
)

vcf_df <- cbind(vcf_df, genotypes_vcf)

header_lines <- c(
  "##fileformat=VCFv4.2",
  "##source=SIM_auto",
  paste("#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO", "FORMAT", 
        paste0("ind", 1:n_individuals, collapse="\t"), sep="\t")
)

output_file <- "simulated_data.vcf"
writeLines(header_lines, con = output_file)
write.table(vcf_df, file = output_file, append = TRUE, 
            quote = FALSE, sep = "\t", row.names = FALSE, col.names = FALSE)

hh_sim <- data2haplohh(
  hap_file = output_file,
  vcf_reader = "vcfR",
  chr.name = 19,
  polarize_vcf = FALSE,
  allele_coding = "01"
)


hh_sim@haplo[1:3, 1:3]
length(hh_sim@positions)

mrk <- names(hh_sim@positions[600])
s <- as.numeric(strsplit(mrk, ':')[[1]][2])
mb <- 1000000000


hap_matrix_r <- hh_sim@haplo[, which(hh_sim@positions >= s & hh_sim@positions < s + mb)]
variant_ids <- colnames(hap_matrix_r)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_r) <- d_mb

cat('Ilość wariantów na prawo od markera :', length(colnames(hap_matrix_r)), '\n')

identity_matrix_r <- calculate_similarity_matrix(hap_matrix_r, reference = 1)
means_r <- calculate_weighted_mean(identity_matrix_r)

hap_matrix_l <- hh_sim@haplo[, which(hh_sim@positions <= s  & hh_sim@positions >= s - mb)]
variant_ids <- colnames(hap_matrix_l)
pos <- as.numeric(sapply(strsplit(variant_ids, ':'), `[`, 2))
d_mb <- (pos + (pos - s))/1000000
colnames(hap_matrix_l) <- d_mb

ord <- order(as.numeric(names(hap_matrix_l[1, ])), decreasing = T)
hap_matrix_l <- hap_matrix_l[, ord]
cat('Ilość wariantów na lewo od markera :', length(colnames(hap_matrix_l)), '\n')

identity_matrix_l <- calculate_similarity_matrix(hap_matrix_l, reference = 1)
means_l <- calculate_weighted_mean(identity_matrix_l)

plot_weighted_means(means_l, x_breaks_step = 150)
plot_weighted_means(means_r, x_breaks_step = 150)
plot_weighted_means_lr(means_l = means_l, means_r = means_r, s = s/1000000,x_breaks_step = 15)
plot(calc_ehhs(hh_sim, mrk = mrk))

