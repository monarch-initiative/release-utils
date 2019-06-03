// Get labels sorted by their frequency
CALL apoc.export.csv.query(
    "CALL apoc.meta.stats()
     YIELD labels with labels, keys(labels) as categories
     UNWIND categories as category
     RETURN category, labels[category]
     ORDER BY labels[category] DESC;",
     "./label-frequency.csv",
     {}
);
