#!/bin/bash

REF_GENOME="/mnt/ip114/DominikPietrzak/DATA/REFERENCE_FILES/human_genome_grch37/human_g1k_v37.fasta"
VCF_IMP_PATH="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/post_imputation_vcf_files"
OUTPUT_VCF="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/post_imputation_merged_vcf/all_chr_imp_merged_filtered_R2_075.vcf.gz"
TEMP_FILTERED_DIR="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/temp_filtered_chunks"
PARALLEL_JOBS=5

mkdir -p "$TEMP_FILTERED_DIR"
mkdir -p "$(dirname "$OUTPUT_VCF")"

filter_chromosome() {
    chr=$1
    input_vcf=$2
    out_dir=$3
    output_vcf="${out_dir}/chr${chr}.filtered.vcf.gz"

    if [ -f "$input_vcf" ]; then
        echo "[START] Filtering chr${chr}..."
        bcftools view -i 'R2>0.75' "$input_vcf" -O z -o "$output_vcf"

        bcftools index -t "$output_vcf"
        echo "[DONE] Chr${chr}"
    else
        echo "[ERROR] File doesn't exsist chr${chr}!"
    fi
}

export -f filter_chromosome

for i in {1..22}; do
    FILE="${VCF_IMP_PATH}/chr${i}.dose.vcf.gz"
    echo "$i $FILE $TEMP_FILTERED_DIR"
done | xargs -P $PARALLEL_JOBS -n 3 bash -c 'filter_chromosome "$@"' _

FILTERED_LIST=""
for i in {1..22}; do
    f="${TEMP_FILTERED_DIR}/chr${i}.filtered.vcf.gz"
    if [ -f "$f" ]; then
        FILTERED_LIST="$FILTERED_LIST $f"
    fi
done

bcftools concat --threads 4 --naive $FILTERED_LIST \
| bcftools norm --threads 4 -f "$REF_GENOME" --check-ref w -O z -o "$OUTPUT_VCF"

bcftools index -t "$OUTPUT_VCF"
rm -rf "$TEMP_FILTERED_DIR"

echo "Finished: $OUTPUT_VCF"
