// Generates counts of unique subject and object node labels and edge types per source
CALL apoc.export.csv.query(
    "MATCH (subject)-[predicate]->(object)
     RETURN labels(subject) as subject_cats, labels(object) as obj_cats, type(predicate),
            count(predicate.isDefinedBy) as count, predicate.isDefinedBy as source",
    "./category-pivot.csv",
     {}
);
