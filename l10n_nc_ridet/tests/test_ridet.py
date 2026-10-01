# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestRidet(TransactionCase):
    def setUp(self):
        super().setUp()
        self.nc = self.env["res.country"].search([("code", "=", "NC")], limit=1)
        self.assertTrue(self.nc, "Country with code NC (New Caledonia) not found")
        self.fr = self.env.ref("base.fr")

    def _create_nc_partner(self, **vals):
        vals.setdefault("name", "Test NC partner")
        vals.setdefault("is_company", True)
        vals.setdefault("country_id", self.nc.id)
        return self.env["res.partner"].create(vals)

    def test_full_ridet_via_siret(self):
        partner = self._create_nc_partner(siret="1234567001")
        self.assertEqual(partner.siren, "1234567")
        self.assertEqual(partner.nic, "001")
        self.assertEqual(partner.siret, "1234567001")
        # Old 9-digit RIDET (6-digit base + 3-digit establishment code)
        partner9 = self._create_nc_partner(siret="015016001")
        self.assertEqual(partner9.siren, "015016")
        self.assertEqual(partner9.nic, "001")
        self.assertEqual(partner9.siret, "015016001")

    def test_ridet_via_siren_nic(self):
        partner = self._create_nc_partner(siren="0833517", nic="001")
        self.assertEqual(partner.siret, "0833517001")

    def test_ridet_base_only(self):
        partner = self._create_nc_partner(siren="0833517")
        self.assertFalse(partner.nic)
        self.assertEqual(partner.siret, "0833517***")
        partner2 = self._create_nc_partner(siret="0833517***")
        self.assertEqual(partner2.siren, "0833517")
        self.assertFalse(partner2.nic)
        # The SIRET placeholder is also accepted, for records
        # that already had one before the country was set to NC
        partner3 = self._create_nc_partner(siret="0833517*****")
        self.assertEqual(partner3.siren, "0833517")
        self.assertFalse(partner3.nic)
        self.assertEqual(partner3.siret, "0833517***")

    def test_ridet_separators(self):
        for siret, expected in [
            ("0833517.001", "0833517001"),
            ("139501-001", "139501001"),
            ("0 833 517 001", "0833517001"),
        ]:
            partner = self._create_nc_partner(siret=siret)
            self.assertEqual(partner.siret, expected, f"Failed for {siret!r}")

    def test_ridet_write_and_clear(self):
        partner = self._create_nc_partner(siren="0833517", nic="001")
        partner.write({"siret": "1234567002"})
        self.assertEqual(partner.siren, "1234567")
        self.assertEqual(partner.nic, "002")
        partner.write({"siret": False})
        self.assertFalse(partner.siren)
        self.assertFalse(partner.nic)
        self.assertFalse(partner.siret)

    def test_wrong_ridet(self):
        vals = {"name": "Wrong NC partner"}
        # Bad lengths
        for siret in ["12345678", "12345670012", "12345"]:
            with self.assertRaises(
                ValidationError, msg=f"SIRET {siret!r} should be rejected"
            ):
                self._create_nc_partner(**dict(vals, siret=siret))
        # Not digits
        with self.assertRaises(ValidationError):
            self._create_nc_partner(**dict(vals, siret="1234567ABC"))
        # A valid French SIRET is not a valid RIDET
        with self.assertRaises(ValidationError):
            self._create_nc_partner(**dict(vals, siret="79237773100023"))
        # French-sized SIREN/NIC are rejected on NC partners
        with self.assertRaises(ValidationError):
            self._create_nc_partner(**dict(vals, siren="792377731", nic="00023"))
        with self.assertRaises(ValidationError):
            self._create_nc_partner(**dict(vals, siren="0833517", nic="00023"))

    def test_french_siret_unchanged(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test FR partner",
                "is_company": True,
                "country_id": self.fr.id,
                "siret": "55555555600011",
            }
        )
        self.assertEqual(partner.siren, "555555556")
        self.assertEqual(partner.nic, "00011")
        partner.write({"siret": "555555556*****"})
        self.assertEqual(partner.siren, "555555556")
        self.assertFalse(partner.nic)
        # A RIDET-shaped value is still rejected on a French partner
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Wrong FR partner",
                    "is_company": True,
                    "country_id": self.fr.id,
                    "siret": "1234567001",
                }
            )

    def test_getters(self):
        partner = self._create_nc_partner(siren="0833517", nic="001")
        self.assertEqual(partner._get_siren(), "0833517")
        self.assertEqual(partner._get_siret(), "0833517001")
        self.assertEqual(partner._get_nic(), "001")
        partner_base_only = self._create_nc_partner(siren="0833517")
        self.assertEqual(partner_base_only._get_siren(), "0833517")
        self.assertFalse(partner_base_only._get_siret())
        self.assertFalse(partner_base_only._get_nic())
        with self.assertRaises(UserError):
            partner_base_only._get_siret(raise_if_none=True)
        partner_empty = self._create_nc_partner()
        self.assertFalse(partner_empty._get_siren())
        with self.assertRaises(UserError):
            partner_empty._get_siren(raise_if_none=True)

    def test_company(self):
        partner = self._create_nc_partner(name="Test NC company", siret="0833517001")
        company = self.env["res.company"].create(
            {
                "name": "Test NC company",
                "partner_id": partner.id,
                "country_id": self.nc.id,
                "currency_id": self.env.ref("base.XPF").id,
            }
        )
        self.assertEqual(company.siret, "0833517001")
        self.assertEqual(company.siren, "0833517")
        self.assertEqual(company.nic, "001")

    def test_nc_vat_consistency_skipped(self):
        # A French VAT number never ends with a 6/7-digit RIDET base,
        # so the French VAT/SIREN consistency check must not apply
        # to New Caledonian partners.
        partner = self._create_nc_partner(
            siren="1234567", nic="001", vat="FR86792377731"
        )
        self.assertEqual(partner.siret, "1234567001")
