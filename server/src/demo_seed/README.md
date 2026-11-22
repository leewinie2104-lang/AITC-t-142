# demo_seed — dữ liệu demo 3 khu

Seed Python chạy lại an toàn (SCRUM-85, plan 004). Nằm ngoài `app/` vì không phải module nghiệp vụ; code `app/` không import nó.
Kịch bản lấy từ `docs/03-design/sql/seed-and-tests.sql` §1–2 (file đó vẫn là nơi chứng minh constraint / RLS).

## Dữ liệu

| Bảng | Số dòng | Nội dung |
|------|---------|----------|
| `zone` | 3 | A, B, C |
| `building` | 6 | A1, ALR (shophouse), APL (bãi công cộng) · B1 · C1, CPL |
| `slot_pool` | 6 | TH1 A1 · TH2 zone A · TH3 A · TH1 B1 · TH2 chain C · TH3 C |
| `slot` | 10 | B2-045 / 046 / 050 / 101, B3-001, TH3-012 / 013 (A) · B1-001 (B) · B1-010, TH3-001 (C) |
| `zone_policy` | 3 | v1 mỗi khu: giá, dự phòng, ngưỡng duyệt, phạm vi mở, mẫu thỏa thuận, quá giờ. **Mặc định, chờ BQL xác nhận** |
| `app_user` | 15 | 5 vai trò (bảng dưới) |
| `consent_record` | 15 | `registration_terms` mỗi tài khoản |
| `asset` / `eligibility` / `slot_holding` | 10 / 10 / 6 | tài sản, tư cách đã duyệt, chủ / người thuê ô |
| `vehicle` | 10 | biển số mã hóa AES-GCM + hash HMAC + dạng che |
| `share_window` / `booking` | 4 / 3 | pilot Tòa A1 (SCRUM-191): lịch chia sẻ của chị A và anh C, anh B thuê ô anh C ngày mai, 2 lượt cũ (anh B quá giờ, anh C về sớm: lịch chia sẻ `closed_early` + `returned_at`). Chưa có `recovery_case` / `parking_request` (cột v6) |

| Tài khoản | Vai trò | Ghi chú |
|-----------|---------|---------|
| `lan`, `binh`, `minh`, `hoa`, `van` | resident | lan giữ TH1 B2-045/046 · minh có tài sản ở A và B (AC-19) · hoa ở B1 → L3 ở C (AC-20) |
| `chi_a`, `anh_b`, `anh_c` | resident | pilot Tòa A1: chị A ô B2-050, anh C ô B3-001 (tầng khác), anh B thuê. Ngày demo = **ngày mai** |
| `tuan` | renter | hợp đồng thuê hết hạn hết ngày hôm qua (AC-22), tự dời theo ngày chạy |
| `khach` | renter | khách vãng lai, L4 |
| `bql_a`, `bql_b`, `bql_c` | zone_manager | mỗi khu một BQL duyệt (BR-18) |
| `guard_a` | guard | bảo vệ khu A |
| `op` | chain_operator | vận hành chuỗi |

Mọi tài khoản dùng chung mật khẩu `SEED_DEMO_PASSWORD`. Seed **không ghi đè** mật khẩu của tài khoản đã có.

ID cố định: `demo_seed.ids.demo_id("<loại>", *khóa)` (UUIDv5), ví dụ `demo_id("user", "lan")`, `demo_id("slot", "A1", "B2-045")`.
Test, CSV LPR (SCRUM-110) và eval dùng lại các ID này; **đổi `NAMESPACE` hoặc khóa là thay đổi phá vỡ**.

## Chạy

Cần trong `.env` (tên biến ở `.env.example`, giá trị lấy từ Bitwarden): `SEED_DEMO=true`, `SEED_DEMO_PASSWORD`, `PLATE_ENC_KEY`, `PLATE_HASH_KEY`, `DATABASE_URL`.
Schema phải có sẵn (migration). Thiếu `SEED_DEMO=true` thì script in "skipped" rồi thoát 0.

```bash
make seed              # hoặc: python server/scripts/seed_demo.py   (chạy từ gốc repo hoặc server/)
make seed DRY=1        # ghi trong transaction, in số liệu, rollback
```

PowerShell không có `make`: `python server/scripts/seed_demo.py` (thêm `--dry-run` nếu cần).

Chạy lại bao nhiêu lần cũng được; mỗi bảng báo `inserted / updated / unchanged`. Sửa `data.py` rồi chạy lại thì chỉ dòng thay đổi được cập nhật.

### Docker compose (postgres local)

```bash
docker compose --profile seed run --rm seed   # postgres → migrate → seed
docker compose --profile app up               # postgres → migrate → seed → api
```

`seed` ép `SEED_DEMO=true` chỉ trong compose local này. Không thêm service này vào compose production.

### DB dùng chung trên CI runner

Kết nối bằng `parksmart_app` (không phải owner, có RLS), và chỉ **một người** seed một lần; không ai khác cần chạy.
Seed tự đổi ngữ cảnh RLS theo nhóm bảng: BQL của cả 3 khu cho `building`, `slot`, `slot_pool`, `zone_policy`, `asset`,
`eligibility`, `slot_holding`; `system` cho `app_user`, `vehicle`, `consent_record`; `system` theo 3 khu cho `share_window`, `booking`.
Muốn làm sạch: xóa volume của DB (`consent_record` chặn UPDATE / DELETE / TRUNCATE nên seed không xóa dữ liệu).

## Log cổng (CSV)

Định dạng chuẩn hóa của ta, 1:1 với `app.lpr_event` (trước khi mã hóa). Job N1 (SCRUM-109) đọc file này; adapter của từng hãng camera (SCRUM-165) chuyển log của hãng về đúng định dạng này.

`source_code,source_event_id,zone_code,gate_code,direction,occurred_at,plate_text,ocr_confidence`

- `source_code`: một camera một làn, **làn quyết định `direction`** (`cam-a1-in` = vào, `cam-a1-out` = ra; B, C tương tự). Cột `direction` giữ lại cho N1.
- `source_event_id`: duy nhất trong nguồn (`zones-NNNN`, `pilot-NNNN`); gửi lại cùng id là trùng (BR-13).
- `occurred_at`: giờ camera, ISO 8601 luôn có offset `+07:00`. N1 dùng cột này, không dùng giờ server nhận.
- `plate_text`: viết như camera in (`30A-123.45`), N1 phải `normalize`. **Rỗng = không đọc được**. Chỉ biển giả; biển lạ có chủ đích nằm trong `UNKNOWN_PLATES`.
- `ocr_confidence`: 0–1, 3 chữ số thập phân; dưới 0.8 thì chờ duyệt tay.

```bash
cd server/src && python -m demo_seed.lpr_csv [--date YYYY-MM-DD] [--out file.csv]   # mặc định: ngày mai, ra stdout
```

Dòng sinh từ `data.py` nên biển luôn khớp xe đã seed; giờ nằm ở `data.CLOCK`. Có 2 bộ: `zones-` (vào / ra mỗi khu, gửi lặp, OCR thấp, không đọc được, biển lạ) và `pilot-` (kịch bản docs/01-product/07-pilot-mot-toa.md §7, gồm lượt ra quá giờ của anh B). Mẫu cố định: `samples/lpr_events_sample.csv` (2026-11-23), chỉ để minh họa.

`ponytail:` chưa mô hình hóa danh sách biển ứng viên top-N của OCR (kiểu OpenALPR); N1 có thể thêm sau cho biển hai dòng.

## Biển số

`app.facility.domain.plate.normalize` (bỏ ký tự phân cách, viết hoa) là dạng chuẩn duy nhất được băm.
`app.platform.crypto.plate_cipher.PlateCipher` mã hóa (AES-256-GCM) và tạo `plate_hash` (HMAC-SHA256).
Dev dùng chung key lấy từ Bitwarden của team (không để trong git, kể cả `.env.example`) để hash giống nhau trên mọi máy. Server demo / production tự sinh key riêng.
Đổi `PLATE_KEY_VERSION` hoặc key thì lần seed sau ghi lại ciphertext và hash.

## Kiểm thử

```bash
cd server && pytest tests/unit/demo_seed tests/unit/facility tests/unit/platform/test_plate_cipher.py
TEST_DATABASE_URL=postgresql://... pytest tests/integration   # DB trống có sẵn schema
```
