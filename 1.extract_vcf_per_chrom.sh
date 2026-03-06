#!/bin/bash

OUTDIR="/mnt/ip114/DominikPietrzak/master_dgr/pliki_vcf_per_chrom"
PFILE="/mnt/ip114/DominikPietrzak/PRS_ANALIZA/DANE_PO_IMPUTACJI_FILTROWANE_PO_JAKOSCI/all_chr_075"

for chr in {1..22}; do
    OUTFILE="$OUTDIR/c${chr}_f.vcf.gz"
    echo "Tworzę VCF dla chromosomu $chr → $OUTFILE"

    plink2 \
        --pfile "$PFILE" \
        --chr "$chr" \
        --rm-dup force-first \
        --recode vcf bgz \
        --out "${OUTFILE%.vcf.gz}"
done
