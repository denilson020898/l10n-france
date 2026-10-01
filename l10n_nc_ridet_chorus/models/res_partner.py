# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _nc_chorus_identifier_type(self):
        """Chorus typeIdentifiantStructure for this partner.

        Returns 'RIDET' for New Caledonian partners, False otherwise
        (let the core SIRET flow handle other countries).
        """
        self.ensure_one()
        country = self.country_id or self.commercial_partner_id.country_id
        if country.code == "NC":
            return "RIDET"
        return False

    def _fr_chorus_api_structures_rechercher(self, api_params, session=None):
        # Non-NC partners: keep the core SIRET behavior untouched.
        nc_partners = self.filtered(lambda p: p._nc_chorus_identifier_type())
        if not nc_partners:
            return super()._fr_chorus_api_structures_rechercher(
                api_params, session=session
            )
        # Duplicated from l10n_fr_chorus_account with RIDET support.
        # Code duplication is intentional: core module must stay SIRET-only.
        self.ensure_one()
        url_path = "structures/v1/rechercher"
        payload = {
            "structure": {
                # siret field holds the full RIDET (9-10 digits) for NC.
                # Use _get_siret() when valid so base-only numbers
                # (*** placeholder) are never sent, with fallback to raw
                # siret to preserve the core behavior otherwise.
                "identifiantStructure": self._get_siret() or self.siret,
                "typeIdentifiantStructure": "RIDET",
            },
        }
        answer, session = self.env["res.company"]._chorus_post(
            api_params, url_path, payload, session=session
        )
        res = False
        if (
            answer.get("listeStructures")
            and len(answer["listeStructures"]) == 1
            and answer["listeStructures"][0].get("idStructureCPP")
        ):
            res = answer["listeStructures"][0]["idStructureCPP"]
        return (res, session)

    def fr_chorus_identifier_get(self):
        # Non-NC partners: keep core behavior (messages mention SIRET).
        nc_partners = self.filtered(
            lambda p: not p.fr_chorus_identifier and p._nc_chorus_identifier_type()
        )
        other_partners = self - nc_partners
        if other_partners:
            super(ResPartner, other_partners).fr_chorus_identifier_get()
        if not nc_partners:
            return
        # Duplicated from l10n_fr_chorus_account for NC partners only,
        # so company (own structure) and customer contacts get the same
        # setup with RIDET-aware messages.
        company2api = {}
        raise_if_ko = self._context.get("chorus_raise_if_ko", True)
        partners = []
        for partner in nc_partners.filtered(lambda p: not p.fr_chorus_identifier):
            if partner.parent_id:
                if raise_if_ko:
                    raise UserError(
                        _("Cannot get Chorus Identifier on partner '%s'.")
                        % partner.display_name
                    )
                logger.warning(
                    "Skipping partner %s: not a contact", partner.display_name
                )
                continue
            if not partner.siren or not partner.nic:
                if raise_if_ko:
                    raise UserError(
                        _("Missing RIDET on partner '%s'.") % partner.display_name
                    )
                logger.warning(
                    "Skipping partner %s: missing RIDET", partner.display_name
                )
                continue
            if (
                partner.invoice_sending_method != "fr_chorus"
                and not self.env.context.get("get_company_identifier")
            ):
                if raise_if_ko:
                    raise UserError(
                        _(
                            "On partner '%s', Invoice Sending "
                            "is not set to 'Chorus Pro'."
                        )
                        % partner.display_name
                    )
                logger.warning(
                    "Skipping partner %s: invoice sending not set to chorus pro",
                    partner.display_name,
                )
                continue
            company = partner.company_id or self.env.company
            if company not in company2api:
                api_params = company._chorus_get_api_params(raise_if_ko=raise_if_ko)
                if not api_params:
                    continue
                company2api[company] = api_params
            partners.append(partner)
        session = None
        for partner in partners:
            company = partner.company_id or self.env.company
            api_params = company2api[company]
            (res, session) = partner._fr_chorus_api_structures_rechercher(
                api_params, session
            )
            if res:
                partner.write({"fr_chorus_identifier": res})
            else:
                identifier = partner._get_siret() or partner.siret
                if raise_if_ko:
                    raise UserError(
                        _(
                            "No entity found in Chorus corresponding to "
                            "RIDET %(identifier)s. "
                            "The detailed error is written in Odoo server logs.",
                            identifier=identifier,
                        )
                    )
                logger.warning(
                    "Skipping partner %s: No entity found in Chorus "
                    "corresponding to RIDET %s.",
                    partner.display_name,
                    identifier,
                )
