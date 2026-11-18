# 11-references — Tài liệu tham khảo

> **Thư mục này trả lời:** dự án dựa vào nguồn bên ngoài nào (văn bản pháp lý, tài liệu kỹ thuật, nghiên cứu), và lấy gì từ đó.

## Tổng quan

**Chưa có tài liệu.** Thư mục này giữ ghi chú về nguồn bên ngoài mà các quyết định của dự án dựa vào. Mỗi ghi chú tóm tắt điều dự án cần và link tới nguồn gốc, không chép nguyên văn.

## Nên có

| File gợi ý | Nội dung | Phục vụ |
|---|---|---|
| `01-legal-parking.md` | Quy định về chỗ đỗ trong nhà chung cư, quyền của chủ sở hữu, nội quy tòa | Giả định A-01, A-08 ([Scope §4](../01-product/03-scope.md)) |
| `02-legal-personal-data.md` | Quy định về dữ liệu cá nhân, biển số, ảnh; chuyển dữ liệu ra nước ngoài | A-03, [Scope §5](../01-product/03-scope.md#5-phụ-thuộc), [09-security](../09-security/README.md) |
| `03-market-pricing.md` | Giá gửi xe tham chiếu, khảo sát nhu cầu | [PRD §8](../01-product/02-prd.md#8-mô-hình-giá-giả-định-từ-nguồn) mô hình giá |
| `04-tech-docs.md` | Link tài liệu LangGraph, Bedrock, FastAPI, arq, pgvector đang dùng | [Tech stack](../02-architecture/02-tech-stack.md) |

## Không đặt ở đây

- Guidebook của ban tổ chức: [docs/guide/](../guide/README.md).
- Quyết định của dự án: [10-adr/](../10-adr/README.md).
- Nội quy mẫu dùng cho RAG (W7): là dữ liệu của hệ thống, đặt cùng seed dữ liệu trong `server/`.

## Quy ước

- Mỗi ghi chú ghi rõ: nguồn (tên văn bản, đường link), ngày truy cập, điều dự án dùng, và tài liệu nào trong repo trích dẫn nó.
- Thông tin pháp lý chỉ để tham khảo; quyết định cuối cùng cần người có thẩm quyền xác nhận.
- File đánh số `NN-`; thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
