// script.js

// Cấu hình đường dẫn API Gateway (Truy cập từ trình duyệt máy ngoài vào Docker)
const BASE_GATEWAY_URL = "http://127.0.0.1:8000"; 

// --- 1. CÁC HÀM XỬ LÝ TOKEN (JWT) ---

function saveToken(token) {
    // Lưu Token vào trình duyệt sau khi đăng nhập thành công
    localStorage.setItem('jwt_token', token);
}

function getAuthHeader() {
    const token = localStorage.getItem('jwt_token');
    // Trả về Header Authorization để gửi kèm các request cần bảo mật
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function getUserIdFromToken(token) {
    try {
        // Giải mã payload của JWT (Phần giữa 2 dấu chấm)
        const payload = token.split('.')[1];
        // atob: giải mã base64 (chỉ hoạt động trên trình duyệt)
        const decoded = JSON.parse(atob(payload)); 
        return decoded.user_id; 
    } catch (e) {
        return null;
    }
}

// --- 2. LOGIC TỰ ĐỘNG CẬP NHẬT HEADER (Login/Logout/Profile) ---
// Đoạn này sẽ chạy ngay khi trang web tải xong để kiểm tra xem user đã đăng nhập chưa

document.addEventListener("DOMContentLoaded", async function() {
    const loginLink = document.getElementById('login-link');
    const logoutLink = document.getElementById('logout-link');
    // Tìm nút đăng ký (nút có class btn-primary trong header-actions)
    const registerBtn = document.querySelector('.header-actions .btn-primary[href="register.html"]'); 

    // Nếu trang hiện tại không có header (ví dụ trang login/register riêng biệt) thì bỏ qua
    if (!loginLink) return;

    const token = localStorage.getItem('jwt_token');
    const userId = localStorage.getItem('user_id');

    if (token && userId) {
        // --- TRẠNG THÁI: ĐÃ ĐĂNG NHẬP ---
        
        // 1. Ẩn nút Đăng ký
        if (registerBtn) registerBtn.style.display = 'none'; 
        
        // 2. Hiện nút Đăng xuất
        if (logoutLink) logoutLink.style.display = 'inline-block';
        
        // 3. Đổi nút Đăng nhập thành Link tới Profile
        loginLink.href = "profile.html"; 
        loginLink.textContent = "👤 Tài khoản của tôi"; // Hiện tạm trước khi tải được tên thật

        // 4. Gọi API lấy tên thật của người dùng để hiển thị cho đẹp
        try {
            const res = await fetch(`${BASE_GATEWAY_URL}/users/users/${userId}`);
            if (res.ok) {
                const user = await res.json();
                // Cập nhật lại thành tên người dùng
                loginLink.textContent = `👤 Chào, ${user.name}`;
            }
        } catch (e) {
            console.log("Không tải được thông tin user header");
        }

    } else {
        // --- TRẠNG THÁI: CHƯA ĐĂNG NHẬP ---
        loginLink.textContent = "Đăng nhập";
        loginLink.href = "login.html";
        
        if (logoutLink) logoutLink.style.display = 'none';
        if (registerBtn) registerBtn.style.display = 'inline-block';
    }

    // --- XỬ LÝ SỰ KIỆN ĐĂNG XUẤT ---
    if (logoutLink) {
        logoutLink.addEventListener('click', function(e) {
            e.preventDefault();
            // Xóa toàn bộ token lưu trong máy
            localStorage.removeItem('jwt_token');
            localStorage.removeItem('user_id');
            // Load lại trang để cập nhật giao diện
            window.location.href = 'index.html';
        });
    }
});

// --- 3. CÁC HÀM TÍCH HỢP SOA (Dùng cho Dashboard/Admin) ---

async function fetchUserName(userId) {
    try {
        // GỌI T1 QUA GATEWAY
        const response = await fetch(`${BASE_GATEWAY_URL}/users/users/${userId}`); 
        if (response.ok) {
            const user = await response.json();
            return user.name || `User ID ${userId}`;
        }
        return `User ID ${userId} (Lỗi truy cập T1)`; 
    } catch (error) {
        return `Lỗi Kết nối T1`;
    }
}

async function fetchCarModelName(carId) {
    try {
        // GỌI T2 QUA GATEWAY
        const response = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars/${carId}`); 
        if (response.ok) {
            const car = await response.json();
            return car.model_name || `Car ID ${carId}`;
        }
        return `Car ID ${carId} (Lỗi truy cập T2)`;
    } catch (error) {
        return `Lỗi Kết nối T2`;
    }
}

async function loadDashboard() {
    const dashboardBody = document.getElementById('orders-table-body');
    const statusMessage = document.getElementById('status-message');
    
    // Kiểm tra xem trang hiện tại có bảng Dashboard không (để tránh lỗi ở các trang khác)
    if (!dashboardBody) return;

    dashboardBody.innerHTML = '<tr><td colspan="5">Đang tải dữ liệu...</td></tr>';
    statusMessage.innerHTML = '';
    
    let orders = [];

    try {
        // GỌI T3 QUA GATEWAY
        const orderResponse = await fetch(`${BASE_GATEWAY_URL}/orders/orders`); 
        
        if (!orderResponse.ok) {
            statusMessage.innerHTML = `Lỗi Tải Đơn Hàng (T3): Server trả về ${orderResponse.status}.`;
            return;
        }
        orders = await orderResponse.json();

    } catch (error) {
        statusMessage.innerHTML = `Lỗi Kết nối Gateway: Đảm bảo Gateway đang chạy trên 8000.`;
        return;
    }
    
    dashboardBody.innerHTML = ''; 
    
    if (orders.length === 0) {
         dashboardBody.innerHTML = '<tr><td colspan="5">Chưa có đơn hàng nào được tạo thành công.</td></tr>';
         return;
    }

    // Tích hợp và hiển thị
    for (const order of orders) {
        const userName = await fetchUserName(order.user_id);
        
        let itemDetails = '';
        for (const item of order.items) {
            const carName = await fetchCarModelName(item.car_model_id);
            const priceVND = item.unit_price.toLocaleString('vi-VN') + ' VND'; 

            itemDetails += `${carName} (${item.quantity} chiếc, ${priceVND}/chiếc)<br>`;
        }
        
        const row = dashboardBody.insertRow();
        row.innerHTML = `
            <td>${order.order_id}</td>
            <td>${userName}</td>
            <td>${itemDetails}</td>
            <td>${order.total_amount.toLocaleString('vi-VN')} VND</td>
            <td><span class="status ${order.status}">${order.status}</span></td>
        `;
    }
}