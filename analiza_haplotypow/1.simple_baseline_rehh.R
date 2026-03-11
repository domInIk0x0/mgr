library(vcfR)
library(progress)
library(rehh)
library(dplyr)
set.seed(123)

# Ekstrakcja formatu haplotypowego
hh <- data2haplohh(hap_file = '/mnt/ip114/DominikPietrzak/master_dgr/pliki_vcf_hla_regions/chr6_hla_28377797_33548354.vcf',
                   vcf_reader = "vcfR",
                   chr.name = 6, polarize_vcf=FALSE,
                   allele_coding = "01",
                   remove_multiple_markers = TRUE
)

# Wykonanie skanu całego haplo w celu policzenia ihh i regionów kandydujących
scan <- scan_hh(hh, phased = TRUE, threads = 28)
ihs <- ihh2ihs(scan)
candidate_regions <- calc_candidate_regions(ihs, threshold = 4, pval = TRUE,
                                            window_size = 1E6, overlap = 1E5,
                                            min_n_extr_mrk = 3)

# Wyciecie danych do wykresu struktury
hh_subset <- subset(hh, select.hap = 1:15, select.mrk = 110:116)
plot(hh_subset, srt.mrk = 30, cex.lab.mrk = 0.73, offset.lab.mrk = 1.4)


# Tabele wynikowe wskaznikow
scan %>% arrange(IHH_A) %>% filter(!is.na(IHH_D)) %>% head(5)
ihs$ihs %>%  arrange(IHS) %>% head(5)
ihs$ihs %>%  arrange(desc(IHS)) %>% head(5)
candidate_regions

# Wybrane warianty
var1 <- '6:28573714:A:G'  #hh@positions[1000]
var2 <- '6:32095725:T:C'  #hh@positions[34800]


analyze_single_variant <- function(x, hap){
  ehh <- calc_ehh(haplohh = hap, mrk = x)
  cat('Częstość allelu ancestralnego: ',ehh$freq[1], '\n')
  cat('Częstość allelu pochodnego: ',ehh$freq[2], '\n')
  plot(ehh)
  
  ehhs <- calc_ehhs(haplohh = hap, mrk = x)
  plot(ehhs, nehhs = FALSE)
  plot(ehhs, nehhs = TRUE)
}

# Wykresy dla wybranych wariantów
analyze_single_variant(var1, hh)
analyze_single_variant(var2, hh)
