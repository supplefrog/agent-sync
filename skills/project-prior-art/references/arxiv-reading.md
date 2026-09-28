# arXiv reading for a project decision

Use this when a quick search reveals competing research approaches or a novel mechanism whose limits could change a project design. Begin with the exact design question and the existing GitHub projects or reference architectures already found. Search relevant arXiv categories and terms; do not manufacture novelty because a local package is absent.

Read the source, not a search snippet. arXiv's export API can return Atom metadata, including ID, title, authors, publication date, abstract, and links:

`https://export.arxiv.org/api/query?search_query=cat:<CATEGORY>+AND+(all:"<term1>"+OR+all:"<term2>")&start=0&max_results=4&sortBy=relevance&sortOrder=descending`

Use the host's ordinary web or raw URL reader. Fetch categories sequentially with a courtesy delay. If a query is thin, widen terms once; report a thin result set rather than padding it. Inspect a paper beyond its abstract when implementation details or empirical claims affect the recommendation. An abstract is a lead, not proof of performance or transferability.

For each relevant paper, record its mechanism, the concrete idea worth borrowing, evidence offered, limitation, and fit to the project's constraints. Keep raw identifiers and links so claims can be checked. For a broad comparative survey, isolated per-paper reads can reduce cross-paper contamination; use them only when the available host supports isolation and the comparison warrants the extra calls. A single careful read is enough for a narrow question.

Converge on the approach most likely to satisfy the project outcome. Compare its implementation burden and known failure modes with existing software that can be reused. Give the first implementable step, the decisive source links, and an observation that would reverse the choice. Do not infer results absent from the fetched paper, or turn a list of papers into an unranked answer.
