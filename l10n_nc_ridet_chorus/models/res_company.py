# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    def _nc_chorus_label(self, partner):
        country = partner.country_id or partner.commercial_partner_id.country_id
        return "RIDET" if country.code == "NC" else "SIRET"

    def _chorus_common_validation_checks(
        self, source_object, invoice_partner, client_order_ref, chorus_service
    ):
        # Duplicated presence checks with RIDET-aware labels so the setup
        # is identical to SIRET for both the own company (supplier) and
        # the customer contact. Presence logic (siren + nic) is the same:
        # full RIDET (base + 3-digit NIC) is required, base-only (***)
        # is rejected, exactly like SIRET with *****.
        # Remaining service/engagement checks are delegated to core
        # to avoid drift (code duplication only where labels differ).
        self.ensure_one()
        company_partner = self.partner_id
        if not company_partner.siren or not company_partner.nic:
            label = self._nc_chorus_label(company_partner)
            raise UserError(
                _(
                    "Missing %(label)s on partner '%(partner)s'"
                    " linked to company '%(company)s'.",
                    label=label,
                    partner=company_partner.display_name,
                    company=self.display_name,
                )
            )
        cpartner = invoice_partner.commercial_partner_id
        if not cpartner.siren or not cpartner.nic:
            label = self._nc_chorus_label(cpartner)
            raise UserError(
                _(
                    "Missing %(label)s on partner '%s'. "
                    "This information is required for Chorus Pro.",
                    label=label,
                )
                % cpartner.display_name
            )
        return super()._chorus_common_validation_checks(
            source_object, invoice_partner, client_order_ref, chorus_service
        )
