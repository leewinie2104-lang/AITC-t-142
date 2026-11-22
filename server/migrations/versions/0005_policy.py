"""policy: zone_policy and current_zone_policy()

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22

Schema v5 section 6, with RLS (20.1) and grants (21).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.zone_policy (
  id                         uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id                    uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  version                    integer NOT NULL CHECK (version > 0),
  effective_from             timestamptz NOT NULL,
  -- The PRD leaves every value below TBD (A-07). DEFAULTS ARE RESEARCHED DEFAULTS, NOT RULES:
  -- "default, confirm with BQL". Rationale and sources per column: docs/03-design/07-db-decision-log.md (D-id in brackets).
  buffer_before              interval NOT NULL DEFAULT '15 minutes'        -- default, confirm with BQL [D-02]
                               CHECK (buffer_before >= interval '0'),
  buffer_after               interval NOT NULL DEFAULT '30 minutes'        -- default, confirm with BQL [D-02]
                               CHECK (buffer_after >= interval '0'),
  approval_threshold_vnd     bigint NOT NULL DEFAULT 1000000               -- default, confirm with BQL [D-08] BR-12
                               CHECK (approval_threshold_vnd >= 0),
  hold_ttl                   interval NOT NULL DEFAULT '10 minutes'        -- default, confirm with BQL [D-16]
                               CHECK (hold_ttl > interval '0'),
  agreement_confirm_ttl      interval NOT NULL DEFAULT '30 minutes'        -- default, confirm with BQL [D-16]
                               CHECK (agreement_confirm_ttl > interval '0'),
  -- BR-16: a running booking survives the expiry of its entitlement for at most this long (NULL = to its end).
  eligibility_grace_max      interval DEFAULT '7 days'                     -- default, confirm with BQL [D-04]
                               CHECK (eligibility_grace_max IS NULL OR eligibility_grace_max >= interval '0'),
  -- Who pays when the owner returns early (AC-09 TBD). Only rule implemented: renter pays the TH3 price for the
  -- relocated period, unused share time is refunded, the provider pays nothing extra.  [D-09]
  early_return_cost_rule     text NOT NULL DEFAULT 'renter_pays_th3_relocated'   -- default, confirm with BQL
                               CHECK (early_return_cost_rule IN ('renter_pays_th3_relocated')),
  -- BR-13: below this OCR confidence an LPR event goes to manual review. v3: moved here from lpr_source
  -- (lpr_source table removed, docs/03-design/08-deferred-tables.md).  [D-21]
  ocr_review_threshold       numeric(4,3) NOT NULL DEFAULT 0.800           -- default, confirm with BQL [D-21]
                               CHECK (ocr_review_threshold BETWEEN 0 AND 1),
  -- BR-19 prices. v3: the price_rule table is merged into this column (docs/03-design/08-deferred-tables.md).
  -- Shape {"TH1"\:{"L1"\:{"hour"\:10000,"day"\:50000},…},…}, integer VND; the rule engine (Pydantic) validates it.
  prices                     jsonb NOT NULL CHECK (jsonb_typeof(prices) = 'object'),
  -- v5 overstay (FR-11, FR-12, BR-08): no overstay table. N2 reminds the renter overstay_pre_reminder before the booking end
  -- and at the end; at exit the rule engine charges nothing up to end + overstay_grace, otherwise
  -- ceil((checked_out_at - end) / overstay_billing_step) * overstay_fee_per_hour_vnd * step / 1 h (billed from the end).
  overstay_pre_reminder      interval NOT NULL DEFAULT '20 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_pre_reminder >= interval '0'),
  overstay_grace             interval NOT NULL DEFAULT '10 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_grace >= interval '0'),
  overstay_fee_per_hour_vnd  bigint NOT NULL DEFAULT 50000                 -- default, confirm with BQL [D-03]; 0 = no fee
                               CHECK (overstay_fee_per_hour_vnd >= 0),
  overstay_billing_step      interval NOT NULL DEFAULT '15 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_billing_step > interval '0'),
  -- Agreement text of this policy version (Markdown with placeholders). v3: the agreement_template table is merged
  -- into this column (docs/03-design/08-deferred-tables.md); agreement.zone_policy_id pins the version used.
  agreement_template_md      text NOT NULL CHECK (btrim(agreement_template_md) <> ''),
  created_by                 uuid REFERENCES app.app_user (id) ON DELETE SET NULL,
  created_at                 timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, version),
  UNIQUE (id, zone_id)
);
CREATE INDEX zone_policy_current_idx ON app.zone_policy (zone_id, effective_from DESC);

-- Policy in force for a zone at a time (latest version already effective).
CREATE FUNCTION app.current_zone_policy(p_zone uuid, p_at timestamptz DEFAULT now())
RETURNS app.zone_policy LANGUAGE sql STABLE AS $$
  SELECT * FROM app.zone_policy p WHERE p.zone_id = p_zone AND p.effective_from <= p_at
  ORDER BY p.effective_from DESC, p.version DESC LIMIT 1
$$;

-- v3: holiday table removed (it fed the N4 forecast, deferred); see docs/03-design/08-deferred-tables.md.

-- Row-Level Security (schema.sql section 20.1) and grants (21).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['zone_policy'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY read_authenticated ON app.%I FOR SELECT
                      USING ((SELECT app.ctx_role()) <> 'anonymous')$p$, t);
    EXECUTE format($p$CREATE POLICY manage_zone ON app.%I FOR ALL
                      USING (app.is_zone_staff(zone_id, '{zone_manager}'))
                      WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'))$p$, t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE ON app.zone_policy TO parksmart_app;
-- Functions created after 0001 get the same treatment as section 21 gives the others.
REVOKE ALL ON FUNCTION app.current_zone_policy(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.current_zone_policy(uuid, timestamptz) TO parksmart_app;
"""
    )


def downgrade() -> None:
    op.execute(
        r"""
DROP FUNCTION IF EXISTS app.current_zone_policy(uuid, timestamptz);
DROP TABLE IF EXISTS app.zone_policy;
"""
    )
