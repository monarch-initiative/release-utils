#!/usr/bin/env bash
# Parse scigraph log file to get clique leader conflicts and convert to tsv

# eg /var/lib/jenkins/jobs/monarch-data-pipeline/builds/$BUILD_NUMBER/log
grep SEVERE $1 |
perl -e '
$pos;
while(<>){
    chomp;
    if ($_ =~ m/.*clique.*/){
        $pos = 1;
    } elsif ($pos == 1){
        $_ =~ s/SEVERE: //;
        print "\n$_"; $pos=2;
    } elsif($pos == 2){
        $_ =~ s/SEVERE: //;
        print "\t$_";
    }
}' |
sed '/^$/d' >clique-warnings.tsv
