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
import json
from json import decoder
import argparse
from enum import Enum
from pathlib import Path
import logging
import yaml
import gzip
import time

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OutputType(str, Enum):
    tsv = 'tsv'
    jsonl = 'jsonl'


OUTPUT_TYPES = set(OutputType._member_names_)


def main():

    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument('--config', '-c', required=True, help='yaml configuration file')
    parser.add_argument('--out', '-o', required=False, help='output directory', default="./")
    parser.add_argument('--output-format', '-O', required=False, help='output format', default="tsv")
    parser.add_argument('--solr', '-s', required=False,
                        default="https://solr-dev.monarchinitiative.org/solr/golr/select",
                        help='solr url')

    args = parser.parse_args()

    if args.output_format not in OUTPUT_TYPES:
        raise ValueError(f"output format not supported, supported formats are {OUTPUT_TYPES}")

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
    solr_request.close()

    for facet in response['facet_counts']['facet_fields']['association_type']:
        association = facet[0]
        file = f"{association}.all.{args.output_format}.gz"
        dump_file_fh = gzip.open(dump_dir / file, 'wt')
        filters = ['association_type:{}'.format(association)]

        if args.output_format == 'tsv':
            generate_tsv(dump_file_fh, args.solr, filters)
        elif args.output_format == 'jsonl':
            generate_jsonl(dump_file_fh, args.solr, filters)

    # Fetch associations configured in args.config
    conf_fh = open(args.config, 'r')
    file_filter_map = yaml.safe_load(conf_fh)

    for directory, file_maps in file_filter_map.items():
        dump_dir = dir_path / directory
        dump_dir.mkdir(parents=True, exist_ok=True)

        for file, filters in file_maps.items():
            dump_file = dump_dir / file
            dump_file_fh = gzip.open(dump_file, 'wt')

            if args.output_format == 'tsv':
                generate_tsv(dump_file_fh, args.solr, filters)
            elif args.output_format == 'jsonl':
                generate_jsonl(dump_file_fh, args.solr, filters)

            dump_file_fh.close()


def generate_tsv(tsv_fh, solr, filters):
    default_fields = \
        'subject,subject_label,subject_taxon,subject_taxon_label,object,'\
        'object_label,relation,relation_label,evidence,evidence_label,source,'\
        'is_defined_by,qualifier'

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

    sesh = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=10, pool_connections=100, pool_maxsize=100)
    sesh.mount('https://', adapter)
    sesh.mount('http://', adapter)
    solr_request = sesh.get(solr, params=count_params)

    facet_response = None
    retries = 10
    for ret in range(retries):
        if facet_response:
            break

        try:
            facet_response = solr_request.json()
            resultCount = facet_response['response']['numFound']

            if resultCount == 0:
                logger.warning("No results found for {}"
                               " with filters {}".format(tsv_fh.name, filters))
        except decoder.JSONDecodeError:
            logger.warning("JSONDecodeError for {}"
                           " with filters {}".format(tsv_fh.name, filters))
            logger.warning("solr content: {}".format(solr_request.text))
            time.sleep(500)

    if not facet_response:
        logger.error("Could not fetch solr docs with for params %s", filters)
        exit(1)

    golr_params['rows'] = 5000
    golr_params['start'] = 0
    golr_params['fq'] = filters

    first_res = True

    while golr_params['start'] < resultCount:
        if first_res:
            golr_params['csv.header'] = 'true'
            first_res = False
        else:
            golr_params['csv.header'] = 'false'

        solr_response = fetch_solr_doc(sesh, solr, golr_params)

        tsv_fh.write(solr_response)
        golr_params['start'] += golr_params['rows']

    sesh.close()


def generate_jsonl(fh, solr, filters):

    #jsonl_writer = jsonlines.open(fh)

    golr_params = {
        'q': '*:*',
        'wt': 'json',
        'fl': '*',
        'fq': filters,
        'start': 0,
        'rows': 1000
    }

    count_params = {
        'wt': 'json',
        'rows': 0,
        'q': '*:*',
        'fq': filters,
    }

    sesh = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=10, pool_connections=100, pool_maxsize=100)
    sesh.mount('https://', adapter)
    sesh.mount('http://', adapter)
    solr_request = sesh.get(solr, params=count_params)

    facet_response = None
    retries = 10
    for ret in range(retries):
        if facet_response:
            break

        try:
            facet_response = solr_request.json()
            resultCount = facet_response['response']['numFound']

            if resultCount == 0:
                logger.warning("No results found for {}"
                               " with filters {}".format(fh.name, filters))
        except decoder.JSONDecodeError:
            logger.warning("JSONDecodeError for {}"
                           " with filters {}".format(fh.name, filters))
            logger.warning("solr content: {}".format(solr_request.text))
            time.sleep(500)

    if not facet_response:
        logger.error("Could not fetch solr docs with for params %s", filters)
        exit(1)

    while golr_params['start'] < resultCount:
        solr_response = fetch_solr_doc(sesh, solr, golr_params)
        docs = json.loads(solr_response)['response']['docs']
        for doc in docs:
            fh.write(f"{json.dumps(doc)}\n")
        golr_params['start'] += golr_params['rows']

    sesh.close()


def fetch_solr_doc(session, solr, params, retries=10):
    solr_response = None

    for ret in range(retries):
        if solr_response:
            break
        try:
            solr_request = session.get(solr, params=params, stream=False)
            solr_response = solr_request.text
        except ChunkedEncodingError:
            logger.warning("ChunkedEncodingError for params %s", params)
            time.sleep(300)

    if not solr_response:
        logger.error("Could not fetch solr docs with for params %s", params)
        exit(1)

    return solr_response


if __name__ == "__main__":
    main()
