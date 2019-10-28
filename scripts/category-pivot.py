"""
Analyze and diff subject category, object category and edge type per source
to sort the output:
sort -t$'\t' -k 4,4 -k 5rn output.tsv >sorted-output.tsv
"""
import argparse
import csv
import ast
import re
from typing import List


def get_most_informative_category(categories: List, descending_freq: List) -> str:
    return descending_freq[max([descending_freq.index(cat) for cat in categories])]


def main():

    parser = argparse.ArgumentParser(
        description='Analyze and diff subject category, object '
                    'category and edge type per source')
    parser.add_argument('--pivot', '-p', type=str, required=True,
                        help='path to pivot table')
    parser.add_argument('--edge_labels', '-e', type=str, required=True,
                        help='path to edge label csv')
    parser.add_argument('--label', '-l', type=str, required=True,
                        help='path to label frequency table')
    parser.add_argument('--output', '-o', type=str, required=False,
                        help='Location of output file', default="./output.tsv")
    args = parser.parse_args()

    # i/o
    output_file = open(args.output, 'w')

    category_frequencies = []
    edge_label_map = {}
    category_source_pivot = {}

    with open(args.label) as csvfile:
        # Create a list where labels are sorted by descending frequency
        # Oddly, Class and NamedIndividual have lower frequencies than
        # other informative labels, such as sequence feature, so we
        # artificially push these to the top
        cat_frequency = csv.reader(csvfile)
        next(cat_frequency)
        for row in cat_frequency:
            category_frequencies.append(row[0])

        # https://stackoverflow.com/a/1014544
        category_frequencies.insert(0, category_frequencies.pop(
            category_frequencies.index("Class")))
        category_frequencies.insert(0, category_frequencies.pop(
            category_frequencies.index("NamedIndividual")))
        category_frequencies.insert(0, category_frequencies.pop(
            category_frequencies.index("cliqueLeader")))

        # Variant is the more informative label
        category_frequencies.insert(0, category_frequencies.pop(
            category_frequencies.index("variant locus")))

    with open(args.edge_labels) as csvfile:
        edge_labels = csv.reader(csvfile)
        next(edge_labels)
        for row in edge_labels:
            iri, label = row
            if label.startswith('['):
                labels = ast.literal_eval(label)
                label = labels[0]
            edge_label_map[iri] = label

    with open(args.pivot) as csvfile:
        cat_pivot = csv.reader(csvfile)
        next(cat_pivot)
        for row in cat_pivot:
            # if not row[4]: continue
            subject_cats = ast.literal_eval(row[0])
            object_cats = ast.literal_eval(row[1])
            subject_category = get_most_informative_category(subject_cats,
                                                             category_frequencies)
            object_category = get_most_informative_category(object_cats,
                                                            category_frequencies)
            # Genes are often
            edge = row[2]
            edge_label = edge_label_map[edge] if edge in edge_label_map else edge

            sources = row[4]
            pivot_count = int(row[3])

            if sources.startswith('['):
                sources = ast.literal_eval(sources)
            else:
                sources = [sources]
            for source in sources:
                if source.startswith("https://data.monarch") or source.startswith("https://archive.monarch"):
                    source = source.replace("https://data.monarchinitiative.org/ttl/", "")
                    source = source.replace("https://archive.monarchinitiative.org/#", "")
                    # source = re.sub(r'\..*$', '', source)
                    table_key = "-".join([
                        subject_category,
                        edge_label,
                        object_category,
                        source
                    ])
                    if table_key in category_source_pivot:
                        category_source_pivot[table_key] += pivot_count
                    else:
                        category_source_pivot[table_key] = pivot_count

    for table_key, pivot_count in category_source_pivot.items():
        output_file.write("\t".join(table_key.split("-")))
        output_file.write("\t{}\n".format(pivot_count))

    output_file.close()


if __name__ == "__main__":
    main()
