# ĐỀ XUẤT — GitHub Actions kiểm thử VinFast SOA (CHƯA TRIỂN KHAI)

Repository mục tiêu: https://github.com/HaoMilke/vinfastsoa

**Trạng thái:** Đề xuất chạy trong nhánh SQA riêng qua Pull Request. Không thay đổi trực tiếp nhánh main; kết quả CI chỉ ghi nhận sau khi GitHub thực thi.

## Mục đích

Chạy kiểm thử tích hợp HTTP ở một bản sao repository trên GitHub-hosted runner Ubuntu với Docker Compose. Mọi DB SQLite đã commit được xóa **chỉ ở working copy của runner** trước khi khởi chạy để tạo dữ liệu thử tách biệt. Các thay đổi tạo người dùng, đơn hàng, trừ tồn chỉ xảy ra trong container CI có vòng đời ngắn. Không dùng môi trường thật.

## Đường dẫn file cần thêm vào repository

- `.github/workflows/vinfast-sqa.yml`: job Docker Compose, chờ service, chạy test, gom log, upload artifact, cleanup.
- `.github/qa/run_integration.py`: kiểm thử API theo mã TC, xuất CSV, JSON, JUnit và trace HTTP đã ẩn mật khẩu/JWT.

File `docker-compose.yml` của dự án nằm trong `VinFast-SOA-Project-master/`.

## Cách dùng sau khi bạn CHẤP THUẬN và các file được commit

1. Workflow chạy tự động khi mở hoặc cập nhật PR từ nhánh CI vào `main`. Trong giai đoạn này không cần merge PR để thử, nhưng GitHub Actions phải đang được bật.
2. Mở PR -> Checks để quan sát run. Job có thể hiện Fail khi kiểm thử phát hiện lỗi thật trong ứng dụng; vẫn có artifact bằng chứng.
3. Chỉ khi nhóm quyết định merge workflow vào `main` thì nút **Actions -> Run workflow** của `workflow_dispatch` mới sẵn dùng trên default branch.
4. Sau khi chạy, mở `Run` -> **Artifacts** -> tải `vinfast-sqa-evidence-<run-id>`; file ZIP chứa: `test_results.csv`, `summary.json`, `junit.xml`, `http_trace.jsonl`, `compose_logs.txt`, `compose_ps.txt`, `baseline.txt`, `docker_version.txt`.
5. Ghi chính xác SHA, run ID và URL run vào báo cáo, tổng hợp Pass/Fail/Blocked/Not Run; **không chuyển test chưa chạy thành Pass**. Với các lỗi kiểm thử, cần mở defect và lưu retest sau khi sửa.

## Những trường hợp được tự động chạy

`TC-01, TC-08, TC-09, TC-12, TC-13, TC-20, TC-25, TC-26, TC-27, TC-28, TC-29, TC-30, TC-31, TC-32, TC-33, TC-36` (16 test).

Đây là những kiểm tra **API/integration** trên hệ thống Docker thật, không phải kiểm thử giao diện trình duyệt. Một số yêu cầu của báo cáo có phạm vi UI rộng hơn; khi cập nhật báo cáo phải nêu rõ phạm vi đã xác minh bằng API. 24 test còn lại giữ `Not Run` cho đến khi có kiểm thử độc lập. Test có tiền điều kiện thất bại được ghi `Blocked`.

Lỗi phát hiện trong một lần CI sẽ làm job hiển thị thất bại, **nhưng bằng chứng vẫn được upload nhờ `if: always()`**. Sau khi sửa code, chạy lại workflow trên commit mới và giữ cả hai bộ log.

## Mức an toàn

- Workflow chỉ có `permissions: contents: read`, không dùng quyền ghi GitHub, không truy cập máy cá nhân, không ghi vào repository từ job.
- Có `pull_request` trigger giới hạn theo nhánh và đường dẫn để chạy bản nháp từ PR, đồng thời có `workflow_dispatch` dùng sau khi file đã nằm ở nhánh mặc định. Không có trigger `push`, không tự merge.
- Không cấp GitHub secrets và không dùng thanh toán thật. JWT chỉ lưu trong RAM của script, trường nhạy cảm bị ẩn trong log HTTP. Tuy nhiên repo có in tài khoản demo vào container log; bước lưu log đã che phần mật khẩu demo.
- **Không chạy script với `--base-url` trỏ đến sản xuất**: script cố ý tạo tài khoản và đơn thử, giảm kho để đo tình trạng rollback.
- `actions/checkout@v4` và `actions/upload-artifact@v4` là các tag phổ biến; trước khi triển khai chính thức, có thể khóa SHA phiên bản theo hướng dẫn bảo mật của GitHub.

## Điều kiện dừng hoặc giới hạn

- Nếu Actions bị vô hiệu hóa ở `Settings`, người có quyền quản trị phải cho phép.
- Nếu `docker compose up --build -d` thất bại do thư viện thiếu tương thích hay cổng không mở được, giữ nguyên `compose_logs.txt`, không khẳng định test đã chạy.
- Nếu một test bị Fail do mã nguồn, không sửa kết quả để workflow xanh. Báo cáo trung thực theo HTTP/log.
- Với mục tiêu báo cáo tối đa 60 trang: trong báo cáo chỉ đưa **bảng tổng hợp và 2–3 ảnh/đoạn log điển hình**, dẫn chiếu link của GitHub Actions run và ZIP minh chứng. Không nhét toàn bộ log vào Word.

## Nguồn tham khảo

- [GitHub Docs — Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub Docs — Managing GitHub Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
- [GitHub Docs — Store and share workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data)
- [Docker Docs — docker compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
