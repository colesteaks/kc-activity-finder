# Updating the source graph

The graph is a maintained research asset. Extend it from observed relationships; do not replace the supplied seed with a freshly invented directory list.

## Add a descendant source

1. Start from an active graph node during a normal sweep.
2. Capture the exact page that links or clearly attributes the first-party target.
3. Confirm the target's canonical URL and ownership.
4. Add a node with an appropriate class such as `event-organizer`, `venue`, `registration-provider`, `ticket-provider`, or `official-calendar`.
5. Add an edge from the discovery node with `observed_at` and the relationship evidence URL.
6. Set provenance to `observed-descendant`, never `provided-seed`.
7. Run both validators.

Add stable sources that improve future sweeps. A one-off event page can remain candidate evidence without becoming a permanent graph node.

## Handle broader-search discoveries

A web supplement can become a descendant only after:

- its first-party ownership is verified;
- a real relationship to the graph is observed and recorded; and
- it is likely to be useful again.

Search rank, popularity, or resemblance to an existing source is not a graph relationship. Keep the candidate labeled `broader-web-search` even if its first-party organizer is later added to the graph.

## Review and retire

- Review active nodes periodically and before relying on them after a long gap.
- Update canonical URLs with evidence when a source moves.
- Mark a dead or unreliable descendant `stale` or `retired`; preserve its provenance and edges for auditability.
- Never delete or silently rewrite the verbatim seed artifact.
- If the user supplies a revised seed artifact, replace `data/primary-sources.txt` only with that explicit input, update its SHA-256 value in `data/source-graph.json`, and reconcile provided-seed nodes line by line.

## Required edge fields

Every persisted edge should contain:

```json
{
  "from": "source-node-id",
  "to": "target-node-id",
  "relationship": "mentions-first-party",
  "evidence_url": "https://source.example/path",
  "observed_at": "2030-01-02T15:04:05-06:00"
}
```

Do not add credentials, private subscriber content, copied article bodies, or personal data to the graph.



## Release and runtime maintenance

Preserve the supplied seed exactly, including capitalization and absence of a trailing newline. The current artifact is only `KC daily`. Do not silently replace it with another file presented as the original. If the user supplies a richer Primary sources.txt, archive the old bytes, record provenance, review the migration, update the hash and provided-seed nodes, then update seed preservation tests accordingly.

Monthly: visit each active route and inspect redirected domains, missing calendars, pagination, PDFs, registration leaves and seasonal feeds. Record actual observed dates. Add official routes with observed relationship evidence; propose unrelated useful sources separately for review. Failed pages are not evidence of no events. Check coverage across all regions and active/passive, adult/kids/family, indoor/outdoor and paid/free categories. Before peak signup seasons, inspect camps, races, leagues and workshops farther ahead.

On every change: install requirements, run repository validation, run all tests, regenerate fictional reports, inspect the diff and confirm no private runs or secrets are included. CI runs the same validation and tests. Run a live smoke sweep only when browsing is available, and label coverage honestly; offline tests do not establish live event accuracy.

Refresh evidence and re-review after any fact, request or ranking change. Resolve conflicts with dated official evidence and retain the prior values in the merge log. Never erase a cancellation or closed signup just to improve the recommendation count.
