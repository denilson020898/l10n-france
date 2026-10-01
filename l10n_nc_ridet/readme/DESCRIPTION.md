New Caledonian companies don't have a French SIRET: they are identified
by a **RIDET** (*Répertoire d'Identification des Entreprises et des
Établissements*), made of a 6 or 7-digit enterprise base number followed
by a 3-digit establishment code, i.e. 9 or 10 digits in total.

The OCA module `l10n_fr_siret` strictly enforces the 14-digit SIRET
format with a Luhn checksum, so a RIDET cannot be entered in the SIRET
field. This module adapts that validation for partners whose country is
**New Caledonia**:

- a 9 or 10-digit RIDET (display separators such as spaces, dots and
  dashes are accepted) can be entered in the SIRET field and is split
  into the SIREN field (RIDET base number) and the NIC field
  (establishment code),
- a base number without establishment code is displayed with a `***`
  suffix (instead of the SIRET `*****` suffix),
- there is no checksum validation on RIDET numbers and the French
  VAT/SIREN consistency check doesn't apply to them.

Partners from other countries, including France, keep the standard
SIRET validation unchanged.
