library(sim1000G)
library(rehh)
library(HaploSim)
library(rehh)
library(vcfR)
library(SNPRelate)
library(SeqArray)


#### Konwersja vcf do gdsa ####
out_dir <- "/mnt/ip114/DominikPietrzak/master_dgr/pliki_gds"
vcf_file <- "/mnt/ip114/DominikPietrzak/master_dgr/pliki_vcf_hla_regions/chr6_hla_28377797_33548354.vcf"

gds_path <- file.path(out_dir, "chr6_hla_28377797_33548354.gds")
seqVCF2GDS(vcf.fn = vcf_file,
           out.fn = gds_path,
           storage.option = "LZMA_RA",  
           parallel = TRUE)

#### Ibs do znalezienia podobnych próbek w danych ####
gds <- seqOpen(gds_path)
ibs <- snpgdsIBS(gds, num.thread = 28)
ibs.dist <- 1 - ibs$ibs

pheatmap(ibs$ibs,
         labels_row = ibs$sample.id,
         labels_col = ibs$sample.id,
         clustering_method = "average",
         main = "IBS similarity heatmap",
         show_rownames = FALSE, 
         show_colnames = FALSE)


#### wybranie probek bazujac na progu w ibs ####
threshold <- 0.8
high_sim <- which(ibs$ibs < threshold, arr.ind = TRUE)
high_sim <- high_sim[high_sim[,1] < high_sim[,2], ]

pairs <- data.frame(
  sample1 = ibs$sample.id[high_sim[,1]],
  sample2 = ibs$sample.id[high_sim[,2]],
  ibs_value = ibs$ibs[high_sim]
)
unique_samples <- unique(c(pairs[,1], pairs[,2]))
cat('Ilość próbek wybranych na podstawie progu: ', length(unique_samples))


#### Generowanie wokol wybranego wariantu ####
var1 <- '6:31264302:A:C' 
region_s <- 31264302 - 1000000
region_end <- 31264302 + 1000000

vcf_s <- readVCF(
  vcf_file, 
  region_start = region_s, 
  region_end = region_end,
  min_maf = 0.001
)

gt1 <- vcf_s$gt1
gt2 <- vcf_s$gt2


#### funkcja do generowania macierzy genotypow ####
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

#### Dodanie próbek ####
new_samples <- colnames(generated_gt1)
vcf_s$individual_ids <- c(vcf_s$individual_ids, new_samples)
vcf_s$gt1 <- cbind(vcf_s$gt1, generated_gt1)
vcf_s$gt2 <- cbind(vcf_s$gt2, generated_gt2)

#### Symulacja przy pomocy 1000g ####
startSimulation(vcf_s, totalNumberOfIndividuals = ncol(vcf_s$gt1))
generateUnrelatedIndividuals(ncol(vcf_s$gt1))

#### Generowanie nowego vcf-a ####
n_individuals <- nrow(SIM$gt1)   
n_variants <- ncol(SIM$gt1)     

genotypes_01 <- SIM$gt1 + SIM$gt2
genotypes_vcf <- matrix(NA, nrow = n_variants, ncol = n_individuals)
unique(as.vector(genotypes_01))

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

output_file <- "/mnt/ip114/DominikPietrzak/master_dgr/plik_wysymulowany_sim1000g/simulated_data.vcf"
writeLines(header_lines, con = output_file)
write.table(vcf_df, file = output_file, append = TRUE, 
            quote = FALSE, sep = "\t", row.names = FALSE, col.names = FALSE)



#### Załodowanie nowego vcfa do formatu happlo ####
hh_sim <- data2haplohh(
  hap_file = output_file,
  vcf_reader = "vcfR",
  chr.name = 6,
  polarize_vcf = FALSE,
  allele_coding = "01"
)
cat('Ilość wariantów: ', length(hh_sim@positions))


mrk <- '6:31300960:G:T'
s <- as.numeric(strsplit(mrk, ':')[[1]][2])
mb <- 1000000000

#### Rysowaanie rozpadu  (lewo/prawo) ####
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


plot_weighted_means(means_l, x_breaks_step = 30)
plot_weighted_means(means_r, x_breaks_step = 30)
plot_weighted_means_lr(means_l = means_l, means_r = means_r, s = s/1000000,x_breaks_step = 15)

plot(calc_ehhs(hh_sim, mrk = '6:31300960:G:T'), nehhs=T)
plot(calc_ehh(hh_sim, mrk = '6:31300960:G:T'))
