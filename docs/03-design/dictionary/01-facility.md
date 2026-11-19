# Từ điển dữ liệu — Cơ sở vật chất và pool (M2, M3)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Cơ sở vật chất và pool (M2, M3)

### zone

Khu đô thị. Đơn vị sở hữu dữ liệu, RLS, giá, duyệt (BR-18). `code` duy nhất toàn hệ thống (một đơn vị vận hành; MVP không có bảng `chain`).  
RLS: **không**

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `code` | text | no |  | Mã nghiệp vụ, duy nhất trong cha của nó. |
| `name` | text | no |  | Tên hiển thị. |
| `timezone` | text | no | 'Asia/Ho_Chi_Minh'::text | Múi giờ IANA cho ngày làm việc địa phương (đối soát, hết hạn vào ngày D). |
| `is_active` | boolean | no | true | Cờ ngừng dùng (xóa mềm); dòng vẫn được lịch sử tham chiếu. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### building

Tòa / cụm shophouse / bãi công cộng. Bãi công cộng là một building loại `public_lot`. Phân khu (tùy chọn) là một mã, không phải bảng.  
RLS: **có** (policy: `manage_zone`, `read_authenticated`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `subzone_code` | text | yes |  | Mã phân khu, tùy chọn (`^[A-Z0-9_-]{1,32}$`); thay bảng `subzone` đã bỏ. |
| `code` | text | no |  | Mã nghiệp vụ, duy nhất trong cha của nó. |
| `name` | text | no |  | Tên hiển thị. |
| `kind` | app.building_kind | no |  | residential_tower · lowrise_cluster · public_lot. |
| `is_active` | boolean | no | true | Cờ ngừng dùng (xóa mềm); dòng vẫn được lịch sử tham chiếu. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### slot_pool

Pool các ô cùng loại kèm phạm vi mở (FR-26). TH1 theo tòa, TH2/TH3 theo khu.  
RLS: **có** (policy: `chain_operator_manage`, `manage_zone`, `read_authenticated`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `building_id` | uuid | yes |  | Có giá trị với pool TH1; NULL với pool TH2/TH3 cấp khu. → `building`. |
| `slot_type` | app.slot_type | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `max_open_scope` | app.open_scope | no |  | Phạm vi rộng nhất nội quy cho phép (TH1 ≤ khu, TH2 ≤ chuỗi, TH3 = công cộng). |
| `investor_consent_at` | timestamp with time zone | yes |  | BR-02: chủ đầu tư đồng ý một lần; bắt buộc với TH2. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### slot

Ô đỗ. Loại TH1/TH2/TH3 chép từ pool, giữ nhất quán bằng FK ghép. `operational_status` cho biết ô có đặt được không.  
RLS: **có** (policy: `manage_zone`, `read_authenticated`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `building_id` | uuid | no |  | Phạm vi tòa, tùy chọn; NULL = cả khu. |
| `pool_id` | uuid | no |  | Pool quyết định loại và phạm vi. → `slot_pool`. |
| `slot_type` | app.slot_type | no |  | TH1 / TH2 / TH3 (chép loại của pool). |
| `level_code` | text | no |  | Tầng đỗ của ô, ví dụ `B2`, `G` (`^[A-Z0-9]{1,8}$`); thay bảng `basement` đã bỏ. |
| `code` | text | no |  | Mã nghiệp vụ, duy nhất trong cha của nó. |
| `size_class` | app.size_class | no |  | Hạng xe lớn nhất ô nhận được: S < M < L < XL (enum có thứ tự). BR-11: `vehicle.size_class <= slot.size_class`. |
| `operational_status` | app.slot_operational_status | no | 'active'::slot_operational_status | `active` (đặt được) · `maintenance` · `blocked`. `booking_validate` từ chối mọi ô không `active`. Thay `is_active`. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |
