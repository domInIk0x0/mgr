#!/bin/bash

mkdir -p /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script_check_result
cd /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script_check_result
perl /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script/HRC-1000G-check-bim.pl   -b /mnt/ip114/DominikPietrzak/DATA/PLINK_FILES/merged_plink.bim   -f /mnt/ip114/DominikPietrzak/DATA/FREQ_FILES/merged_freq.frq   -r /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_tab/HRC.r1-1.GRCh37.wgs.mac5.sites.tab   -h
