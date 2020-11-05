from monarch.markdown import add_md_header, add_href, add_md_table,\
    add_bold, add_italics
from typing import List, Dict, Union, Any, Set, Tuple
from requests import Request, Session
from json.decoder import JSONDecodeError
from pathlib import Path
import logging
import copy
import re
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JSONType = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]


def get_version_metadata(scigraph_prod: str, scigraph_dev: str) -> str:
    """
    :param scigraph_prod:
    :param scigraph_dev:
    :return:
    """
    output_md = str()
    query = "dynamic/datasets.json"

    dev_request = requests.get(scigraph_dev + query, timeout=120)
    prod_request = requests.get(scigraph_prod + query, timeout=120)
    try:
        dev_response = dev_request.json()
    except JSONDecodeError as json_exc:
        raise JSONDecodeError(
               "Cannot parse scigraph response for {}: {}".format(dev_request.url, json_exc.msg),
               json_exc.doc,
               json_exc.pos
        )

    try:
        prod_response = prod_request.json()
    except JSONDecodeError as json_exc:
        raise JSONDecodeError(
               "Cannot parse scigraph response for {}: {}".format(prod_request.url, json_exc.msg),
               json_exc.doc,
               json_exc.pos
        )

    dev_version = _process_scigraph_datasets(dev_response)
    prod_version = _process_scigraph_datasets(prod_response)

    output_md += 'Production build: '
    output_md += add_href(prod_version, prod_version)
    output_md += '  \n'

    output_md += 'Beta build: '
    output_md += add_href(dev_version, dev_version)

    return output_md

def _process_scigraph_datasets(dataset_graph) -> str:
    """
    :param dataset_graph:
    :return: version
    """
    version = ''
    for edge in dataset_graph['edges']:
        if edge['pred'] == 'dcat:distribution':
            if edge['sub'].endswith('#ncbigene'):
                version = edge['sub']\
                    .replace('MonarchArchive:', 'https://archive.monarchinitiative.org/')\
                    .replace('/#ncbigene', '')
                break

    return version



def get_scigraph_category_diff(scigraph_prod: str, scigraph_dev: str) -> str:

    category_cypher = "MATCH (n) RETURN labels(n) AS NodeType, count(n) AS NumberOfNodes"

    cypher_endpoint = 'cypher/execute.json'

    prod_url = scigraph_prod + cypher_endpoint
    dev_url = scigraph_dev + cypher_endpoint

    output_md = str()
    prod_results = get_scigraph_results(prod_url, category_cypher, limit=1000)
    dev_results = get_scigraph_results(dev_url, category_cypher, limit=1000)

    if prod_results == 'timeout' or dev_results == 'timeout':
        formatted_diff = {"request timeout": '0'}
    else:
        diff = diff_facets(_process_scigraph_categories(dev_results), _process_scigraph_categories(prod_results))
        formatted_diff = convert_diff_to_md(diff)

    params = {
        'cypherQuery': category_cypher,
        'limit': 1000
    }

    sesh = Session()
    prod_req = sesh.prepare_request(Request('GET', prod_url, params=params))
    dev_req = sesh.prepare_request(Request('GET', dev_url, params=params))

    output_md += add_href(prod_req.url, "Production Query")
    output_md += '  \n'
    output_md += add_href(dev_req.url, "Dev Query")
    output_md += '  \n\n'

    diff_list = [(k, v) for k, v in formatted_diff.items()]
    diff_list.sort(key=lambda tup: int(re.search(r'[\d,]+', tup[1]).group(0).replace(',', '')), reverse=True)
    output_md += add_md_table(diff_list, ['Category', 'Count'])
    output_md += "\n\n"

    return output_md


def get_scigraph_diff(scigraph_prod: str, scigraph_dev: str,
                      conf: dict, query_name: str) -> str:
    output_md = str()
    cypher_endpoint = 'cypher/execute.json'

    prod_url = scigraph_prod + cypher_endpoint
    dev_url = scigraph_dev + cypher_endpoint

    prod_results = get_scigraph_results(prod_url, conf['query'])[0]
    dev_results = get_scigraph_results(dev_url, conf['query'])[0]
    if prod_results == 'timeout' or dev_results == 'timeout':
        formatted_diff = {"request timeout": '0'}
    else:
        diff = diff_facets(dev_results, prod_results)
        formatted_diff = convert_diff_to_md(diff)

    output_md += "{}\n".format(add_md_header(query_name, 3))

    params = {
        'cypherQuery': conf['query']
    }

    sesh = Session()
    prod_req = sesh.prepare_request(Request('GET', prod_url, params=params))
    dev_req = sesh.prepare_request(Request('GET', dev_url, params=params))

    output_md += add_href(prod_req.url, "Production Query")
    output_md += '  \n'
    output_md += add_href(dev_req.url, "Dev Query")
    output_md += '  \n\n'

    diff_list = [(k, v) for k, v in formatted_diff.items()]
    diff_list.sort(key=lambda tup: int(re.search(r'[\d,]+', tup[1]).group(0).replace(',', '')), reverse=True)
    output_md += add_md_table(diff_list, conf['headers'])
    output_md += "\n\n"

    return output_md


def get_facets(solr_server: str,
               params: Dict[str, Union[str, List[str]]]) -> Tuple[Dict[str, int], Dict[str,str]]:
    facet_map = {}  # facet clean label to facet key dictionary
    solr_request = requests.get(solr_server, params=params)
    response = solr_request.json()
    facet = params['facet.field']
    result_count = response['response']['numFound']
    facet_result = response['facet_counts']['facet_fields'][facet]
    facet_obj = {}
    for facet_key, facet_count in zip(facet_result[::2], facet_result[1::2]):
        facet_original = facet_key
        if facet_key.startswith('http'):
            facet_key = Path(facet_key).stem.replace("#", "")
        # For odd species and strain nomenclature
        facet_key = \
            facet_key.replace('/', '|').replace('(', '|').replace(')', '|').replace('<', '').replace('>', '')
        facet_obj[facet_key] = facet_count
        facet_map[facet_key] = facet_original

    res_sum = sum([v for k, v in facet_obj.items()])

    # Note that this only works for scalars, so setting other to 0 for list fields
    other_count = 0
    if facet not in ['is_defined_by']:
        other_count = result_count - res_sum
    facet_obj['Total'] = result_count
    facet_obj['Other'] = other_count
    return facet_obj, facet_map


def get_scigraph_results(scigraph_server: str, query: str, limit=None) -> JSONType:
    params = {
        'cypherQuery': query
    }
    if limit:
        params['limit'] = limit

    scigraph_request = requests.get(scigraph_server, params=params, timeout=120)
    try:
        response = scigraph_request.json()
    except JSONDecodeError as json_exc:
        #raise JSONDecodeError(
        #       "Cannot parse scigraph response for {}: {}".format(scigraph_request.url, json_exc.msg),
        #       json_exc.doc,
        #       json_exc.pos
        #)
        logging.info("Cannot parse scigraph response for {}: {}".format(scigraph_request.url, json_exc.msg))
        response = ["timeout"]

    return response


def diff_facets(query: Dict[str, int], reference: Dict[str, int]) -> Dict[str, Tuple[int,int]]:
    diff_obj = copy.deepcopy(query)
    for key in reference:
        if key not in query:
            query[key] = 0
    for key in query:
        if key not in reference:
            reference[key] = 0
        diff = query[key] - reference[key]
        diff_obj[key] = (query[key], diff)

    return diff_obj


def convert_diff_to_md(diff: Dict[str, Tuple[int, int]]) -> Dict[str, List[int]]:
    diff_obj = copy.deepcopy(diff)
    for k, v in diff.items():
        count, diff = v
        if diff == 0:
            diff_obj[k] = "{:,} ({:,})".format(count, diff)
        elif diff > 0:
            diff_obj[k] = "{:,} (+{})".format(count, add_bold(diff))
        else:
            diff_obj[k] = "{:,} (-{})".format(count, add_italics(abs(diff)))

    return diff_obj


def diff_solr_so_data(
        query: Dict[str, Set[str]],
        reference: Dict[str, Set[str]]
) -> Dict[str, Set[str]]:
    results = {}
    for sub in reference:
        results[sub] = set()
        try:
            results[sub] = reference[sub] - query[sub]
        except KeyError:
            results[sub] = reference[sub]

    return results


def get_solr_so_pairs(
        solr_server: str,
        params: Dict[str, Union[str, List[str]]]) -> Dict[str, Set[str]]:
    results = {}
    params['start'] = 0
    params['rows'] = 1000

    result_count = params['rows']

    while params['start'] < result_count:
        solr_request = requests.get(solr_server, params=params)
        response = solr_request.json()
        result_count = response['response']['numFound']
        if result_count == 0:
            break
        for doc in response['response']['docs']:
            try:
                results[doc['subject']].add(doc['object'])
            except KeyError:
                results[doc['subject']] = {doc['object']}

        params['start'] += params['rows']
    return results


def _process_scigraph_categories(results) -> Dict[str,int]:
    # dictionary of category:count, eg Node:1000
    category_counts = {}
    for result in results:
        for category in result['NodeType']:
            if category in category_counts:
                category_counts[category] += result['NumberOfNodes']
            else:
                category_counts[category] = result['NumberOfNodes']

    return category_counts
