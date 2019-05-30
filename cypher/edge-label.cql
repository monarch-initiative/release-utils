// Get edge iris and their labels
CALL apoc.export.csv.query(
    "CALL db.relationshipTypes()
     YIELD relationshipType
     MATCH (node:Node{iri:relationshipType})
     RETURN node.iri, node.label",
     "./edge-label.csv",
     {}
);
