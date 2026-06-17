#!/bin/bash

set -e

IN_DIR="/mnt/ip114/DominikPietrzak/master_dgr/pliki_vcf_per_chrom"
OUT_REG_DIR="/mnt/ip114/DominikPietrzak/master_dgr/pliki_vcf_region_for_test"
OUT_LD_DIR="${OUT_REG_DIR}/ld_matrixes_for_test"


CHROMS=(1 2 4 5 7 9 11 13 14 15 17 18 19 20 21 22)


for CHR in "${CHROMS[@]}"; do
    echo "========================================"
    echo "Przetwarzanie chromosomu ${CHR}..."

    VCF_IN="${IN_DIR}/c${CHR}_f.vcf.gz"

    if [[ ! -f "${VCF_IN}" ]]; then
        echo "Błąd: Nie znaleziono pliku ${VCF_IN}. Pomijam..."
        continue
    fi

    echo "Skanowanie wariantów (limit: 15 000)..."


    POSITIONS=$(gzip -cd "${VCF_IN}" | grep -v "^#" | awk '
        NR==1 {start=$2}
        {end=$2}
        NR==15000 {print start, end; exit}
        END {if(NR<15000) print start, end}
    ')

    START_BP=$(echo "${POSITIONS}" | awk '{print $1}')
    END_BP=$(echo "${POSITIONS}" | awk '{print $2}')

    if [[ -z "${START_BP}" || -z "${END_BP}" ]]; then
        echo "Błąd: Brak danych o pozycjach dla chromosomu ${CHR}."
        continue
    fi

    echo "Wykryto region z max 15000 wariantów: od ${START_BP} do ${END_BP}"

    BASENAME="chr${CHR}_reg_${START_BP}_${END_BP}"

    echo "Krok 1/2: Wycinanie regionu i zapisywanie jako .vcf..."
    plink2 --vcf "${VCF_IN}" \
           --chr "${CHR}" \
           --from-bp "${START_BP}" \
           --to-bp "${END_BP}" \
           --keep-allele-order \
           --export vcf \
           --out "${OUT_REG_DIR}/${BASENAME}"

    VCF_OUT="${OUT_REG_DIR}/${BASENAME}.vcf"

    echo "Krok 2/2: Generowanie macierzy LD (.vcor)..."

    plink2 --vcf "${VCF_OUT}" \
           --r2-phased \
           --ld-window-r2 0 \
           --ld-window 9999999 \
           --ld-window-kb 99999 \
           --out "${OUT_LD_DIR}/${BASENAME}_matrix"

    echo "Zakończono przetwarzanie chromosomu ${CHR}."
done

echo "========================================"
echo "Done"
