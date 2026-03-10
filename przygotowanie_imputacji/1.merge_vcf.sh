#!/bin/bash

ls /mnt/ip114/DominikPietrzak/DATA/RAW_VCF_FILES/c{1..22}.vcf.gz | sort -V > /mnt/ip114/DominikPietrzak/DATA/VCF_FILES/merge_vcf_list.txt
bcftools concat -f /mnt/ip114/DominikPietrzak/DATA/VCF_FILES/merge_vcf_list.txt -o merged_vcf.vcf.gz
tabix -p vcf /mnt/ip114/DominikPietrzak/DATA/VCF_FILES/merged_vcf.vcf.gz
