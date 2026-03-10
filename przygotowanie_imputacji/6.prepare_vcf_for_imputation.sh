#!/bin/bash

INPUT_DIR="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/updated_plink_files"
OUTPUT_DIR="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/pre_imputation_vcf_files"
SAMPLES_TO_REMOVE="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/samples_to_remove.txt"
REFERENCE="/mnt/ip114/DominikPietrzak/DATA/REFERENCE_FILES/human_genome_grch37/human_g1k_v37.fasta"
PLINK_CMD="/home/dpietrzak/plink_module/plink"
mkdir -p "$OUTPUT_DIR"

for chr in {1..22}; do
    echo "Processing chromosome $chr..."

    $PLINK_CMD --bfile "$INPUT_DIR/merged_plink-updated-chr$chr" \
          --recode vcf \
          --out "$OUTPUT_DIR/chr${chr}.temp"

    base="$OUTPUT_DIR/chr${chr}.temp"
    
    if [ ! -f "$base.vcf" ]; then
        echo "Error: for chrom $chr"
        continue
    fi

    bcftools view -S ^"$SAMPLES_TO_REMOVE" -Oz "$base.vcf" \
    | bcftools +fixref -Oz -o "$OUTPUT_DIR/chr${chr}_unsorted.vcf.gz" -- -f "$REFERENCE" -m ref-alt

    bcftools sort "$OUTPUT_DIR/chr${chr}_unsorted.vcf.gz" -Oz -o "$OUTPUT_DIR/chr${chr}_clean.vcf.gz"
    
    tabix -p vcf "$OUTPUT_DIR/chr${chr}_clean.vcf.gz"

    rm "$base.vcf" "$base.log" "$base.nosex" "$OUTPUT_DIR/chr${chr}_unsorted.vcf.gz"

    echo "Chromosome $chr done."
done
