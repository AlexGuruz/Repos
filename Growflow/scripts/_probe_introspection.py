import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.growflow_graphql import graphql_request

c = "E:/secrets/gcp/growflowapi.txt"
queries = [
    'query { __type(name: "Query") { fields { name } } }',
    'query { __type(name: "Product") { name fields { name } } }',
]
for q in queries:
    try:
        r = graphql_request(q, credentials_path=c)
        print("Q:", q[:60])
        print(" ", r.get("errors") or "data keys", list((r.get("data") or {}).keys()))
    except Exception as e:
        print("Q:", q[:60], "ERR", e)
