"""Payment (VietQR mock) with overstay guard

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQL copied from docs/03-design/sql/schema.sql (v5); RLS and grants live in the same revision as the table (ADR-0005).


def upgrade() -> None:
    op.execute("""
-- v3: the voucher table (shophouse vouchers, FR-22) is removed (docs/03-design/08-deferred-tables.md); with it go
-- payment.voucher_id, payment.discount_vnd and the payment_validate_voucher trigger, and the gross/discount
-- pair collapses into a plain amount_vnd.
CREATE TABLE app.payment (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  booking_id      uuid NOT NULL,
  payer_user_id   uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  kind            app.payment_kind NOT NULL,
  amount_vnd      bigint NOT NULL CHECK (amount_vnd >= 0),
  -- charge: payer_user_id pays; refund: payer_user_id is the person refunded (D-09).
  direction       text GENERATED ALWAYS AS (CASE WHEN kind = 'early_return_refund' THEN 'refund' ELSE 'charge' END) STORED,
  provider        text NOT NULL DEFAULT 'vietqr_mock' CHECK (provider = 'vietqr_mock'),  -- A-05: no real money
  status          app.payment_status NOT NULL DEFAULT 'pending',
  idempotency_key text NOT NULL UNIQUE,
  paid_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  CHECK ((status = 'paid_simulated') = (paid_at IS NOT NULL))
);
CREATE INDEX payment_booking_idx ON app.payment (booking_id);
CREATE INDEX payment_payer_idx ON app.payment (payer_user_id, created_at DESC);
-- At most one successful payment per booking and kind (so also one paid overstay_fee per booking).
CREATE UNIQUE INDEX payment_paid_uq ON app.payment (booking_id, kind) WHERE status = 'paid_simulated';

-- v5: an overstay fee exists only once the car has left (N1 set checked_out_at). Defence in depth for the rule engine.
-- SECURITY DEFINER: the payer's RLS context may not see the booking row.
CREATE FUNCTION app.payment_overstay_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  v_out timestamptz;
  v_found boolean;
BEGIN
  SELECT b.checked_out_at, true INTO v_out, v_found FROM app.booking b WHERE b.id = NEW.booking_id;
  IF v_found IS TRUE AND v_out IS NULL THEN       -- unknown booking: let the foreign key report it
    RAISE EXCEPTION 'overstay_fee needs a checked-out booking (checked_out_at is NULL for %)', NEW.booking_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER payment_overstay_guard BEFORE INSERT OR UPDATE OF kind, booking_id ON app.payment
  FOR EACH ROW WHEN (NEW.kind = 'overstay_fee') EXECUTE FUNCTION app.payment_overstay_guard();

-- updated_at maintenance (v5 section 18)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['payment'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

-- RLS (v5 section 20.5)
ALTER TABLE app.payment ENABLE ROW LEVEL SECURITY;
CREATE POLICY payer ON app.payment FOR ALL
  USING (payer_user_id = (SELECT app.ctx_user_id())) WITH CHECK (payer_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.payment FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

-- Grants (v5 section 21)
GRANT SELECT, INSERT, UPDATE ON app.payment TO parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;
REVOKE ALL ON FUNCTION app.payment_overstay_guard() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.payment_overstay_guard() TO parksmart_app;
""")


def downgrade() -> None:
    op.execute("""
DROP TABLE app.payment;
DROP FUNCTION app.payment_overstay_guard();
""")
