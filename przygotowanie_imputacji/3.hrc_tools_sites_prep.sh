#!/bin/bash

mkdir -p /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_tab
mkdir -p /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script
wget -P /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script http://www.well.ox.ac.uk/~wrayner/tools/HRC-1000G-check-bim-v4.2.7.zip
wget -P /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_tab ftp://ngs.sanger.ac.uk/production/hrc/HRC.r1-1/HRC.r1-1.GRCh37.wgs.mac5.sites.tab.gz
gunzip -k /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_tab/HRC.r1-1.GRCh37.wgs.mac5.sites.tab.gz
unzip -d /mnt/ip114/DominikPietrzak/VCF_IMPUTATION_PREP/HRC/hrc_script   /mnt/ip114/DominikPietrzak/gene/VCF_PREPARATION/HRC/hrc_script/HRC-1000G-check-bim-v4.2.7.zip
