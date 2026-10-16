// Reviewed templates used by the application. Supply parameters in a company
// graph authorized for the current user; do not run against arbitrary graphs.
// Source: workweave-api/workweave_api/tools.py -- trace_impact
MATCH path=(o:Entity {entity_type:'SalesOrder',active:true})-[:DEPENDS_ON*1..4]->(target:Entity {id:$id,active:true})
WHERE all(n IN nodes(path) WHERE n.active=true)
MATCH (o)-[:DEPENDS_ON]->(po:Entity {entity_type:'PurchaseOrder',active:true})
OPTIONAL MATCH (o)-[:DEPENDS_ON]->(product:Entity {entity_type:'Product',active:true})
RETURN DISTINCT o.payload AS order_json, po.payload AS po_json, product.payload AS product_json,
    [n IN nodes(path) | n.id] AS path_ids ORDER BY o.required_date;

// Source: tools.py -- find_owner. $id is resolved against current source data.
MATCH (e:Entity {id:$id,active:true})-[:OWNED_BY]->(t:Entity {active:true})
RETURN t.name AS name, t.id AS id;

// Source: retrieval.py -- graph expansion from retrieved entity IDs.
MATCH path=(seed:Entity {active:true})-[:DEPENDS_ON|OWNED_BY*1..2]->(related:Entity {active:true})
WHERE seed.id IN $ids AND all(n IN nodes(path) WHERE n.active=true)
RETURN related.payload AS payload, [n IN nodes(path) | n.id] AS ids LIMIT 24;

// Source: retrieval.py -- lexical retrieval, before current-version filtering.
CALL db.idx.fulltext.queryNodes('Chunk',$query) YIELD node, score
RETURN node.payload AS payload, score ORDER BY score DESC LIMIT 30;

// Source: retrieval.py -- vector retrieval; requires compatible indexed vectors.
CALL db.idx.vector.queryNodes('Chunk','embedding',30,vecf32($vector)) YIELD node, score
RETURN node.payload AS payload, score ORDER BY score DESC;

// Source: store.py -- persisted memory/state lookup; $kind may be 'episode',
// 'conversation', 'run', or another approved record kind.
MATCH (n:Record {id:$id,kind:$kind}) RETURN n.payload AS payload;

// Source: graph.py -- indexes created once for each graph.
CREATE INDEX FOR (n:Record) ON (n.id);
CREATE FULLTEXT INDEX FOR (n:Chunk) ON (n.text);
CREATE VECTOR INDEX FOR (n:Chunk) ON (n.embedding)
OPTIONS {dimension:768, similarityFunction:'cosine'};

// Inspection only: this is an example for FalkorDB Browser, not an agent tool.
MATCH (a)-[r]->(b) RETURN a, r, b LIMIT 50;
