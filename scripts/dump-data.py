#!/usr/bin/python3
""" Monarch Data Dump Script

This script is used to dump tsv files from the
Monarch association index

The input is a yaml configuration with the format:

directory_name:
  file_name.tsv:
  - solr_filter_1
  - solr_filter_2
"""
import requests
import argparse
from pathlib import Path
import logging
import yaml
import gzip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():

    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument('--config', '-c', required=True, help='yaml configuration file')
    parser.add_argument('--out', '-o', required=False, help='output directory', default="./")
    parser.add_argument('--solr', '-s', required=False,
                        default="https://solr-dev.monarchinitiative.org/solr/golr/select",
                        help='solr url')

    args = parser.parse_args()
    dir_path = Path(args.out)

    # Fetch all associations

    association_dir = 'all_associations'
    dump_dir = dir_path / association_dir
    dump_dir.mkdir(parents=True, exist_ok=True)

    # wt=json&facet=true&json.nl=arrarr&rows=0&q=*:*&facet.field=association_type
    assoc_params = {
        'q': '*:*',
        'wt': 'json',
        'json.nl': 'arrarr',
        'rows': 0,
        'facet': 'true',
        'facet.field': 'association_type'
    }

    solr_request = requests.get(args.solr, params=assoc_params)
    response = solr_request.json()

    for facet in response['facet_counts']['facet_fields']['association_type']:
        association = facet[0]
        file = "{}.all.tsv.gz".format(association)
        dump_file_fh = gzip.open(dump_dir / file, 'wt')
        filters = ['association_type:{}'.format(association)]
        generate_tsv(dump_file_fh, args.solr, filters)

    # Fetch associations configured in args.config
    conf_fh = open(args.config, 'r')
    file_filter_map = yaml.safe_load(conf_fh)

    for directory, file_maps in file_filter_map.items():
        dump_dir = dir_path / directory
        dump_dir.mkdir(parents=True, exist_ok=True)

        for file, filters in file_maps.items():
            dump_file = dump_dir / file
            dump_file_fh = dump_file.open("w")

            generate_tsv(dump_file_fh, args.solr, filters)

            dump_file_fh.close()


def generate_tsv(tsv_fh, solr, filters):
    default_fields = '''
        subject,subject_label,subject_taxon,subject_taxon_label,
        object,object_label,relation,relation_label,evidence,evidence_label,
        source,is_defined_by,qualifier
    '''

    golr_params = {
        'q': '*:*',
        'wt': 'csv',
        'csv.encapsulator': '"',
        'csv.separator': '\t',
        'csv.header': 'true',
        'csv.mv.separator': '|',
        'fl': default_fields
    }

    for filter in filters:
        if filter == 'association_type:disease_phenotype':
            golr_params['fl'] += ',onset,onset_label,frequency,frequency_label'

    count_params = {
        'wt': 'json',
        'rows': 0,
        'q': '*:*',
        'fq': filters,
    }
    solr_request = requests.get(solr, params=count_params)
    response = solr_request.json()
    resultCount = response['response']['numFound']

    if resultCount == 0:
        logger.warn("No results found for {}"
                    " with filters {}".format(tsv_fh.name, filters))

    golr_params['rows'] = 1000
    golr_params['start'] = 0
    golr_params['fq'] = filters

    first_res = True

    while golr_params['start'] < resultCount:
        if first_res:
            golr_params['csv.header'] = 'true'
            first_res = False
        else:
            golr_params['csv.header'] = 'false'
        solr_request = requests.get(solr, params=golr_params)
        solr_response = solr_request.text
        tsv_fh.write(solr_response)
        golr_params['start'] += golr_params['rows']


if __name__ == "__main__":
    main()

