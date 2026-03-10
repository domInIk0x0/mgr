#!/bin/bash

PLINK_CMD="/home/dpietrzak/plink_module/plink"
RESULT_DIR="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/updated_plink_files"
HRC_CHECK="/mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script_check_result"
PLINK_BFILE="/mnt/ip114/DominikPietrzak/DATA/PLINK_FILES/merged_plink"

mkdir -p "$RESULT_DIR"
cd $RESULT_DIR



$PLINK_CMD --bfile "$PLINK_BFILE" \
      --exclude "$HRC_CHECK/Exclude-merged_plink-HRC.txt" \
      --make-bed --out TEMP1


$PLINK_CMD --bfile TEMP1 \
      --update-map "$HRC_CHECK/Chromosome-merged_plink-HRC.txt" \
      --update-chr --make-bed --out TEMP2

$PLINK_CMD --bfile TEMP2 \
      --update-map "$HRC_CHECK/Position-merged_plink-HRC.txt" \
      --make-bed --out TEMP3

$PLINK_CMD --bfile TEMP3 \
      --flip "$HRC_CHECK/Strand-Flip-merged_plink-HRC.txt" \
      --make-bed --out TEMP4

$PLINK_CMD --bfile TEMP4 \
      --reference-allele "$HRC_CHECK/Force-Allele1-merged_plink-HRC.txt" \
      --make-bed --out merged_plink-updated

for chr in {1..22}; do
    echo "chrom $chr..."
    $PLINK_CMD --bfile merged_plink-updated \
          --reference-allele "$HRC_CHECK/Force-Allele1-merged_plink-HRC.txt" \
          --make-bed --chr $chr \
          --out "merged_plink-updated-chr$chr"
done

rm TEMP1.* TEMP2.* TEMP3.* TEMP4.*
