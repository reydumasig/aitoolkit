"""
create_search_index.py

Creates (or recreates) the Azure AI Search index used by Ops Assistant.

Requirements:
  pip install azure-search-documents

Env vars (required):
  AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
  AZURE_SEARCH_KEY=...

Env vars (optional):
  AZURE_SEARCH_INDEX=opsassistant-docs
  EMBEDDING_DIM=3072   # text-embedding-3-large default; use 1536 for text-embedding-3-small
  RECREATE_INDEX=true  # delete + recreate if exists
"""

import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SemanticSettings,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
)

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "opsassistant-docs")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "3072"))
RECREATE = os.getenv("RECREATE_INDEX", "false").lower() in ("1", "true", "yes", "y")

if not SEARCH_ENDPOINT or not SEARCH_KEY:
    raise SystemExit("Missing AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_KEY")

credential = AzureKeyCredential(SEARCH_KEY)
client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)

VECTOR_PROFILE_NAME = "content-vector-profile"
HNSW_CONFIG_NAME = "hnsw-config"


def index_exists(name: str) -> bool:
    try:
        client.get_index(name)
        return True
    except Exception:
        return False


def build_index() -> SearchIndex:
    # Core fields:
    # - id: unique chunk id (key)
    # - docId: source document id (filterable)
    # - filename/docType: metadata
    # - chunkId: chunk number
    # - content: chunk text
    # - contentVector: embedding vector for retrieval
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="docId", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="docType", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="blobName", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="authorityLevel", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="chunkId", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="pageNumber", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="sectionTitle", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            analyzer_name="en.lucene",
        ),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIM,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=HNSW_CONFIG_NAME,
                parameters=HnswParameters(
                    m=4,
                    ef_construction=200,
                    ef_search=100,
                    metric="cosine",
                ),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=HNSW_CONFIG_NAME,
            )
        ],
    )

    semantic = SemanticSettings(
        configurations=[
            SemanticConfiguration(
                name="semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=None,
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[
                        SemanticField(field_name="filename"),
                        SemanticField(field_name="docType"),
                    ],
                ),
            )
        ]
    )

    return SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_settings=semantic,
    )


def main():
    exists = index_exists(INDEX_NAME)
    if exists and RECREATE:
        print(f"Deleting existing index: {INDEX_NAME}")
        client.delete_index(INDEX_NAME)
        exists = False

    if exists:
        print(f"Index already exists: {INDEX_NAME}")
        print("Set RECREATE_INDEX=true to delete and recreate.")
        return

    index = build_index()
    client.create_index(index)
    print(f"Created index: {INDEX_NAME}")
    print(f"Vector dims: {EMBEDDING_DIM}")
    print(f"Vector profile: {VECTOR_PROFILE_NAME}")
    print(f"HNSW config: {HNSW_CONFIG_NAME}")


if __name__ == "__main__":
    main()

"""
Notes:
- Set EMBEDDING_DIM=3072 for text-embedding-3-large or 1536 for text-embedding-3-small.
- This script creates a vector-enabled index using Azure AI Search's vector index schema pattern.
"""
