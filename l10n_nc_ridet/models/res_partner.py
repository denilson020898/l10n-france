# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

NC_COUNTRY_CODE = "NC"
# A RIDET is made of an enterprise base number (6 digits for old numbers,
# 7 digits for recent ones) followed by a 3-digit establishment code,
# i.e. 9 or 10 digits in total. Unlike the SIREN/SIRET, it has no checksum.
RIDET_BASE_LENGTHS = (6, 7)
RIDET_NIC_LENGTH = 3
RIDET_FULL_LENGTHS = (9, 10)
RIDET_NIC_PLACEHOLDER = "***"
SIRET_NIC_PLACEHOLDER = "*****"
# Separators commonly used when a RIDET is displayed, e.g. "0833517.001",
# "139501-001" or "0 833 517 001".
RIDET_SEPARATORS_RE = re.compile(r"[\s.\-]")


def normalize_ridet(value):
    """Remove the display separators from a RIDET, without touching
    the '***' placeholder used when the establishment code is unknown."""
    return RIDET_SEPARATORS_RE.sub("", value or "")


def is_valid_ridet_base(value):
    return bool(value) and value.isdigit() and len(value) in RIDET_BASE_LENGTHS


def is_valid_ridet_nic(value):
    return bool(value) and value.isdigit() and len(value) == RIDET_NIC_LENGTH


def is_valid_ridet(value):
    value = normalize_ridet(value)
    return bool(value) and value.isdigit() and len(value) in RIDET_FULL_LENGTHS


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _is_nc_ridet(self):
        """Whether this partner uses a New Caledonian RIDET instead of
        a French SIRET. Contacts without a country of their own follow
        the country of their commercial partner."""
        self.ensure_one()
        country = self.country_id or self.commercial_partner_id.country_id
        return country.code == NC_COUNTRY_CODE

    @api.depends("siren", "nic", "country_id")
    def _compute_siret(self):
        super()._compute_siret()
        for partner in self:
            if partner.siren and not partner.nic and partner._is_nc_ridet():
                partner.siret = partner.siren + RIDET_NIC_PLACEHOLDER

    def _inverse_siret(self):
        nc_partners = self.filtered(lambda partner: partner._is_nc_ridet())
        super(ResPartner, self - nc_partners)._inverse_siret()
        for partner in nc_partners:
            partner._inverse_ridet()

    def _inverse_ridet(self):
        self.ensure_one()
        if not self.siret:
            self.write({"siren": False, "nic": False})
            return
        value = normalize_ridet(self.siret)
        if is_valid_ridet(value):
            base, nic = value[:-3], value[-3:]
            vals = {"siren": base, "nic": nic}
            if self.siret != value:
                # On create/write, Odoo stores the assigned value as-is and
                # protects it against recomputation while the inverse runs,
                # so normalize the stored value here (e.g. "0833517.001"
                # becomes "0833517001"). The recursive inverse call this
                # triggers is a no-op because the value is already canonical.
                vals["siret"] = value
            self.write(vals)
            return
        for placeholder in (RIDET_NIC_PLACEHOLDER, SIRET_NIC_PLACEHOLDER):
            base = value[: -len(placeholder)]
            if value.endswith(placeholder) and is_valid_ridet_base(base):
                vals = {"siren": base, "nic": False}
                if self.siret != base + RIDET_NIC_PLACEHOLDER:
                    vals["siret"] = base + RIDET_NIC_PLACEHOLDER
                self.write(vals)
                return
        raise ValidationError(_("RIDET '%s' is invalid.") % self.siret)

    @api.constrains("siren", "nic", "vat")
    def _check_siret(self):
        nc_partners = self.filtered(lambda partner: partner._is_nc_ridet())
        super(ResPartner, self - nc_partners)._check_siret()
        for partner in nc_partners:
            partner._check_ridet()

    def _check_ridet(self):
        """Check the RIDET base number and establishment code.
        There is no checksum on RIDET numbers and the French VAT
        consistency check doesn't apply to them."""
        self.ensure_one()
        if self.type == "contact" and self.parent_id:
            return
        if self.nic and not is_valid_ridet_nic(self.nic):
            raise ValidationError(
                _(
                    "The RIDET establishment code '{nic}' of partner "
                    "'{partner_name}' is incorrect: it must have exactly "
                    "3 digits."
                ).format(nic=self.nic, partner_name=self.display_name)
            )
        if self.siren and not is_valid_ridet_base(self.siren):
            raise ValidationError(
                _(
                    "The RIDET base number '{siren}' of partner "
                    "'{partner_name}' is incorrect: it must have 6 or "
                    "7 digits."
                ).format(siren=self.siren, partner_name=self.display_name)
            )

    def _get_siren(self, raise_if_none=False):
        self.ensure_one()
        if self._is_nc_ridet():
            partner = self.parent_id or self
            if partner.siren and is_valid_ridet_base(partner.siren):
                return partner.siren
            if raise_if_none:
                raise UserError(
                    _("RIDET base number is not set on partner '%s'.")
                    % partner.display_name
                )
            return None
        return super()._get_siren(raise_if_none=raise_if_none)

    def _get_siret(self, raise_if_none=False):
        self.ensure_one()
        if self._is_nc_ridet():
            if (
                self.siren
                and self.nic
                and is_valid_ridet_base(self.siren)
                and is_valid_ridet_nic(self.nic)
            ):
                return self.siret
            if raise_if_none:
                raise UserError(
                    _("RIDET is not set on partner '%s'.") % self.display_name
                )
            return None
        return super()._get_siret(raise_if_none=raise_if_none)

    def _get_nic(self, raise_if_none=False):
        self.ensure_one()
        if self._is_nc_ridet():
            if (
                self.siren
                and self.nic
                and is_valid_ridet_base(self.siren)
                and is_valid_ridet_nic(self.nic)
            ):
                return self.nic
            if raise_if_none:
                raise UserError(
                    _("RIDET establishment code is not set on partner '%s'.")
                    % self.display_name
                )
            return None
        return super()._get_nic(raise_if_none=raise_if_none)
