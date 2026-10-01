Chorus Pro support for New Caledonian RIDET numbers.

Unlike mainland France (14-digit SIRET), New Caledonian suppliers are
identified by a 9 or 10-digit RIDET. Chorus Pro expects
`typeIdentifiantStructure = RIDET` with the RIDET as `identifiantStructure`
for suppliers, while recipients stay SIRET-based.

This glue module (auto-installed when both `l10n_nc_ridet` and
`l10n_fr_chorus_account` are present) duplicates the minimal Chorus
lookup/validation logic with RIDET support, so OCA core modules stay
SIRET-only:

- supplier (own company, `res.company.partner_id`) and customer contact
  (`res.partner`) share the same setup: full identifier (`siren` + `nic`)
  required, base-only (`***` / `*****`) rejected,
- `structures/v1/rechercher` payload uses `RIDET` for `NC` partners,
  `SIRET` otherwise (delegated to core),
- Factur-X (`l10n_fr_account_invoice_facturx`) needs no change: the `siret`
  field already holds the full RIDET and is sent when `siren` + `nic`
  are set.
