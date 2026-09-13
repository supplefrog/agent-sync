# Paper APIs and citation metadata

Adapted from Hermes Agent's MIT-licensed `arxiv` skill. This reference retains its paper-search, citation-graph, and bibliography guidance under the source-acquisition owner; the standalone entry is disabled, not deleted.

## arXiv lookup

Use the stdlib helper from this skill's directory:

```text
python scripts/search_arxiv.py "transformer attention" --max 5
python scripts/search_arxiv.py --author "Yann LeCun" --max 5
python scripts/search_arxiv.py --category cs.AI --sort date --max 5
python scripts/search_arxiv.py --id 1706.03762v1 --max 1
python scripts/search_arxiv.py --id 2402.03300,2401.12345
```

Use the working host Python, not an assumed `python3`. Sort choices are `relevance`, `date`, and `updated`. The helper's abstracts are previews, not complete evidence. Its links preserve the returned version suffix.

For advanced queries or pagination, request `https://export.arxiv.org/api/query` directly with URL-encoded parameters:

- `search_query`: field prefixes `all:`, `ti:`, `au:`, `abs:`, `cat:`, `co:`; explicit `AND`, `OR`, `ANDNOT`, parentheses, and quoted phrases. A URL `+` encodes a space, not an AND operator.
- Example decoded expression: `au:hinton AND cat:cs.LG` or `ti:"chain of thought"`.
- `id_list`: comma-separated exact IDs, including versions when requested.
- `start`: zero-based offset; `max_results`: a bounded requested page size.
- `sortBy`: `relevance`, `submittedDate`, or `lastUpdatedDate`; `sortOrder`: `ascending` or `descending`.

The API returns Atom XML. Parse with Python XML utilities, not shell text matching. Preserve title, full abstract, all authors, published/updated dates, categories, versioned ID, and source links. `totalResults` is the query's declared total, not proof of complete collection; deduplicate and check pagination before claiming coverage.

Make arXiv calls sequentially, with at least a few seconds between requests. On HTTP 429, respect Retry-After and stop tight retries. If the API remains unavailable, use the paper's official abstract/HTML/PDF page for a known ID; label search or pagination coverage unverified. Never fill missing API results from invented metadata.

## Read and validate

- Abstract: `https://arxiv.org/abs/{versioned_id}`.
- Full content: `https://arxiv.org/html/{versioned_id}` where available, otherwise `https://arxiv.org/pdf/{versioned_id}` via the source reader. For local PDFs use `document-files`.
- Preserve modern IDs and legacy IDs such as `hep-th/0601001` literally. Validate supplied identifiers rather than silently repairing them.
- Unversioned URLs resolve to the latest revision; citations must name the version actually read. Preserve the API's versioned ID.
- Inspect withdrawal/retraction notices and incomplete metadata before treating a paper as normal evidence. Abstracts establish only what they explicitly say; retrieve the full text for implementation or result claims.
- Category examples: `cs.AI`, `cs.CL`, `cs.CV`, `cs.LG`, `cs.IR`, `cs.SE`, `cs.CR`, `stat.ML`, `math.OC`. Verify unfamiliar categories against https://arxiv.org/category_taxonomy.

## Semantic Scholar

Use for citation graphs and related-paper discovery, not as proof of a paper's claims. Check current API access requirements and limits at https://api.semanticscholar.org/api-docs/; do not assume an API key guarantees quota or a fixed public request rate.

Base: `https://api.semanticscholar.org/graph/v1`.

| Need | Path and parameters |
|---|---|
| Paper details | `/paper/arXiv:{id}?fields=title,authors,year,abstract,citationCount,referenceCount,influentialCitationCount,externalIds` |
| DOI lookup | `/paper/DOI:{doi}?fields=title,authors,year,externalIds` |
| Papers citing this one | `/paper/arXiv:{id}/citations?fields=title,authors,year,citationCount&limit=10` |
| This paper's references | `/paper/arXiv:{id}/references?fields=title,authors,year,citationCount&limit=10` |
| Search | `/paper/search?query={encoded_query}&limit=5&fields=title,authors,year,citationCount,externalIds` |
| Author search | `/author/search?query={encoded_name}&fields=name,hIndex,citationCount,paperCount` |

Additional useful fields: `isOpenAccess`, `openAccessPdf`, `fieldsOfStudy`, and `publicationVenue`. Author-name matches are candidates, not identity proof. Citations and h-index are contextual indicators, not quality verdicts.

Recommendations use the documented POST query at `https://api.semanticscholar.org/recommendations/v1/papers/` with `positivePaperIds` and optional `negativePaperIds`. Use real returned paper IDs and check the current schema. Follow returned pagination tokens/offsets and back off on rate limits; an empty or failed request is not absence of related work.

## BibTeX

Build entries only from retrieved metadata. Include title, complete author list joined with `and`, publication year, exact versioned `eprint`, `archivePrefix = {arXiv}`, the actual primary category, and the versioned source URL. Escape BibTeX-sensitive characters and use a stable unique citation key. Do not invent a primary category, venue, DOI, or publication status when missing. If citing a journal/conference edition instead, verify its metadata and distinguish it from the preprint. Use `grounded-citations` for claim-to-source evidence in prose.
