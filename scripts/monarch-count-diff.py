#!/usr/bin/python3
""" Monarch Data Diff

Generate a diff of solr facet counts
and scigraph queries as markdown and html
"""
from requests import Request, Session
import argparse
from pathlib import Path
import logging
import yaml
import copy
import re
import markdown
from monarch.markdown import add_md_header, add_href, add_md_table
from monarch.util import get_scigraph_category_diff, get_facets, get_scigraph_diff,\
    get_solr_so_pairs, diff_solr_so_data, diff_facets, convert_diff_to_md

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():

    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument('--config', '-c', required=True, help='yaml configuration file')
    parser.add_argument('--out', '-o', required=False, help='output directory', default="./")
    parser.add_argument('--threshold', '-t', required=False, help='diff threshold', default=10, type=int)
    parser.add_argument('--quick', required=False, help='Do not dump data diffs',
                        default=False, action='store_true')
    args = parser.parse_args()
    dir_path = Path(args.out)
    dir_path.mkdir(exist_ok=True)
    threshold = float(args.threshold/100)

    solr_diff_path = dir_path / 'solr-diff.md'
    solr_diff_file = solr_diff_path.open("w")

    diff_html_path = dir_path / 'solr-diff.html'
    diff_html_file = diff_html_path.open("w")

    rules_path = dir_path / 'monarch-rules.md'
    rules_file = rules_path.open("w")

    rules_html_path = dir_path / 'monarch-rules.html'
    rules_html_file = rules_html_path.open("w")

    scicat_path = dir_path / 'scigraph-categories.md'
    scicat_file = scicat_path.open("w")

    scicat_html_path = dir_path / 'scigraph-categories.html'
    scicat_html_file = scicat_html_path.open("w")

    golr_facet_params = {
        'q': '*:*',
        'wt': 'json',
        'rows': '0',
        'facet': 'true',
        'facet.limit': '3000',
        'facet.mincount': '1',
        'facet.sort': 'count',
        'indent': 'on'
    }

    golr_default_params = {
        'q': '*:*',
        'wt': 'json',
        'fl': 'subject,object'
    }

    conf_fh = open(args.config, 'r')
    config = yaml.safe_load(conf_fh)

    solr_dev = config['solr-dev']
    solr_prod = config['solr-prod']
    scigraph_data_dev = config['scigraph-data-dev']
    scigraph_data_prod = config['scigraph-data-prod']
    scigraph_ontology_dev = config['scigraph-ontology-dev']
    scigraph_ontology_prod = config['scigraph-ontology-prod']

    solr_diff_file.write("{}\n".format(add_md_header("Solr Queries", 2)))

    # Process solr queries
    for q_name, query in config['solr_facet_queries'].items():
        golr_facet_params['fq'] = query['filters']
        golr_facet_params['facet.field'] = query['facet.field']
        prod_results, prod_facet_map = get_facets(solr_prod, golr_facet_params)
        dev_results, dev_facet_map = get_facets(solr_dev, golr_facet_params)
        diff = diff_facets(dev_results, prod_results)
        formatted_diff = convert_diff_to_md(diff)

        # Create a filtered object based on the threshold passed in (or 10%)
        # If there is a x% decrease in data pass this on to generate a data
        # diff
        if args.quick or ('skip_diff' in query and query['skip_diff']):
            filtered_diff = {}
        else:
            filtered_diff = {k:v for k,v in diff.items()
                             if (v[0] == 0 and v[1] < 0) or
                             (v[1] < 0 and 1 - v[0] / (v[0] + abs(v[1])) >= threshold)}

        for dropped_data in filtered_diff:
            if dropped_data == 'Total' or \
                   dropped_data.startswith(":.well-known"):
                continue

            diff_dir = dir_path / q_name.replace(' ', '_').lower()
            diff_dir.mkdir(parents=True, exist_ok=True)

            diff_path = diff_dir / "{}.tsv".format(dropped_data.replace(' ', '_').lower())
            diff_file = diff_path.open("w")

            params = copy.deepcopy(golr_default_params)
            params['fq'] = copy.deepcopy(query['filters'])
            if dropped_data == 'Other':
                params['fq'].append('-{}:[* TO *]'.format(query['facet.field']))
            else:
                params['fq'].append('{}:"{}"'.format(query['facet.field'], prod_facet_map[dropped_data]))
            logger.info("Processing data diff for params {}".format(params['fq']))

            query_pairs = get_solr_so_pairs(solr_dev, params)
            reference_pairs = get_solr_so_pairs(solr_prod, params)

            solr_diff = diff_solr_so_data(query_pairs, reference_pairs)
            for sub, objects in solr_diff.items():
                for obj in objects:
                    diff_file.write("{}\t{}\n".format(sub, obj))
            diff_file.close()

        solr_diff_file.write("{}\n".format(add_md_header(q_name, 3)))
        sesh = Session()
        prod_req = sesh.prepare_request(Request('GET', solr_prod, params=golr_facet_params))
        dev_req = sesh.prepare_request(Request('GET', solr_dev, params=golr_facet_params))

        solr_diff_file.write(add_href(prod_req.url, "Production Query"))
        solr_diff_file.write('\n\n')
        solr_diff_file.write(add_href(dev_req.url, "Dev Query"))
        solr_diff_file.write('\n\n')

        diff_list = [(k, v) for k, v in formatted_diff.items()]
        diff_list.sort(key=lambda tup: int(re.search(r'\d+', tup[1]).group(0)), reverse=True)
        solr_diff_file.write(add_md_table(diff_list, query['headers']))
        solr_diff_file.write('\n\n')

    solr_diff_file.close()
    solr_diff_file = solr_diff_path.open("r")
    html = markdown.markdown(solr_diff_file.read(), output_format='html5', extensions=['markdown.extensions.tables'])
    diff_html_file.write(html)
    diff_html_file.close()
    solr_diff_file.close()

    ######## Monarch Rules ###
    ##########################

    rules_file.write("{}\n".format(add_md_header("Monarch Rules", 2)))

    for q_name, query in config['monarch_rules']['scigraph_data_queries'].items():
        rules_file.write(get_scigraph_diff(
            scigraph_data_prod, scigraph_data_dev, query, q_name))

    for q_name, query in config['monarch_rules']['scigraph_ontology_queries'].items():
        rules_file.write(get_scigraph_diff(
            scigraph_ontology_prod, scigraph_ontology_dev, query, q_name))

    rules_file.close()
    rules_file = rules_path.open("r")
    html = markdown.markdown(rules_file.read(), output_format='html5', extensions=['markdown.extensions.tables'])
    rules_html_file.write(html)
    rules_html_file.close()
    rules_file.close()


    ######## Scigraph categories ###
    ################################

    scicat_file.write("{}\n".format(add_md_header("SciGraph Categories", 2)))

    # Get categories for dev
    scicat_file.write(get_scigraph_category_diff(scigraph_data_prod, scigraph_data_dev))

    scicat_file.close()
    scicat_file = scicat_path.open("r")
    html = markdown.markdown(scicat_file.read(), output_format='html5', extensions=['markdown.extensions.tables'])
    scicat_html_file.write(html)
    scicat_html_file.close()
    scicat_file.close()


if __name__ == "__main__":
    main()
