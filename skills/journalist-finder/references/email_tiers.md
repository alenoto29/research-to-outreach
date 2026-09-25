# Email evidence tiers

An email tier labels how an address entered the record. It is not a claim of deliverability.

| Tier | Evidence | `confirmed` |
|---|---|---|
| A published | Address is directly published on a source page for that person/organization; preserve the source URL. | true |
| A verified | An explicitly authorized verifier returned a valid result; preserve provider and status. | true |
| B pattern | Address was composed from a documented domain pattern; not published for this person. | false |
| C desk | Generic editorial/contact address, not a person's address. | false |
| unresolved | No supported address. Do not include in contact-ready output. | false |

Never fabricate an address or promote a pattern-derived address to published/verified status.
