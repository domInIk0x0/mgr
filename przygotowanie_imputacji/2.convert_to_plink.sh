#!/bin/bash

plink1_9 --vcf /mnt/ip114/DominikPietrzak/DATA/VCF_FILES/merged_vcf.vcf.gz --make-bed --out /mnt/ip114/DominikPietrzak/DATA/PLINK_FILES/merged_plink
plink1_9 --freq --bfile /mnt/ip114/DominikPietrzak/DATA/PLINK_FILES/merged_plink --out /mnt/ip114/DominikPietrzak/DATA/FREQ_FILES/merged_freq
