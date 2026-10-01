# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestChorusRidet(TransactionCase):
    def setUp(self):
        super().setUp()
        self.nc = self.env["res.country"].search([("code", "=", "NC")], limit=1)
        self.assertTrue(self.nc, "Country NC not found")
        self.fr = self.env.ref("base.fr")
        self.Company = self.env["res.company"]
        self.Partner = self.env["res.partner"]

    def _create_partner(self, country, **vals):
        vals.setdefault("name", "Test partner")
        vals.setdefault("is_company", True)
        vals.setdefault("country_id", country.id)
        return self.Partner.create(vals)

    def test_identifier_type(self):
        nc = self._create_partner(self.nc, siren="0833517", nic="001")
        fr = self._create_partner(self.fr, siret="55555555600011")
        self.assertEqual(nc._nc_chorus_identifier_type(), "RIDET")
        self.assertFalse(fr._nc_chorus_identifier_type())

    def test_rechercher_payload_nc(self):
        partner = self._create_partner(
            self.nc, siren="0833517", nic="001", invoice_sending_method="fr_chorus"
        )
        captured = {}

        def fake_post(self, api_params, url_path, payload, session=None):
            captured.update(payload)
            return ({"listeStructures": [{"idStructureCPP": 12345}]}, session)

        with patch.object(
            type(self.env["res.company"]), "_chorus_post", fake_post
        ):
            res, _session = partner._fr_chorus_api_structures_rechercher(
                {"login": "x", "password": "y", "qualif": True}, session=None
            )
        self.assertEqual(res, 12345)
        self.assertEqual(
            captured["structure"]["typeIdentifiantStructure"], "RIDET"
        )
        self.assertEqual(captured["structure"]["identifiantStructure"], "0833517001")

    def test_rechercher_payload_fr_untouched(self):
        partner = self._create_partner(
            self.fr,
            siret="55555555600011",
            invoice_sending_method="fr_chorus",
        )
        captured = {}

        def fake_post(self, api_params, url_path, payload, session=None):
            captured.update(payload)
            return ({"listeStructures": [{"idStructureCPP": 6789}]}, session)

        with patch.object(
            type(self.env["res.company"]), "_chorus_post", fake_post
        ):
            res, _session = partner._fr_chorus_api_structures_rechercher(
                {"login": "x", "password": "y", "qualif": True}, session=None
            )
        self.assertEqual(res, 6789)
        self.assertEqual(captured["structure"]["typeIdentifiantStructure"], "SIRET")
        self.assertEqual(
            captured["structure"]["identifiantStructure"], "55555555600011"
        )

    def test_identifier_get_nc_customer(self):
        partner = self._create_partner(
            self.nc, siren="0833517", nic="001", invoice_sending_method="fr_chorus"
        )
        with (
            patch.object(
                type(partner.company_id or self.env.company),
                "_chorus_get_api_params",
                lambda self, raise_if_ko=False: {"qualif": True},
            ),
            patch.object(
                type(self.env["res.company"]),
                "_chorus_post",
                lambda self, api_params, url_path, payload, session=None: (
                    {"listeStructures": [{"idStructureCPP": 4242}]},
                    session,
                ),
            ),
        ):
            partner.fr_chorus_identifier_get()
        self.assertEqual(partner.fr_chorus_identifier, 4242)

    def test_common_validation_nc_company_and_customer(self):
        company_partner = self._create_partner(self.nc, siret="0833517001")
        company = self.Company.create(
            {
                "name": "NC company",
                "partner_id": company_partner.id,
                "country_id": self.nc.id,
                "currency_id": self.env.ref("base.XPF").id,
            }
        )
        customer = self._create_partner(self.nc, siret="1234567001")
        # source_object only needs display_name and _name
        company._chorus_common_validation_checks(customer, customer, False, False)

    def test_common_validation_base_only_rejected(self):
        company_partner = self._create_partner(self.nc, siren="0833517")
        company = self.Company.create(
            {
                "name": "NC base-only company",
                "partner_id": company_partner.id,
                "country_id": self.nc.id,
                "currency_id": self.env.ref("base.XPF").id,
            }
        )
        customer = self._create_partner(self.nc, siret="1234567001")
        with self.assertRaises(UserError):
            company._chorus_common_validation_checks(customer, customer, False, False)
