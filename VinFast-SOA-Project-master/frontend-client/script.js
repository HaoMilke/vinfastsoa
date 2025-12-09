// script.js

// BASE_GATEWAY_URL là cổng của API Gateway (T4), chạy trên cổng 8000
const BASE_GATEWAY_URL = "http://127.0.0.1:8000"; 

// --- CÁC HÀM XỬ LÝ PHIÊN (SESSION) ---

function saveToken(token) {
    // Lưu Token vào trình duyệt sau khi đăng nhập thành công
    localStorage.setItem('jwt_token', token);
}

function getAuthHeader() {
    const token = localStorage.getItem('jwt_token');
    // Trả về Header Authorization để gửi đến Gateway/Back-end
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function getUserIdFromToken(token) {
    // Giải mã payload của JWT để lấy user_id đã nhúng vào (Payload là phần giữa 2 dấu chấm)
    try {
        const payload = token.split('.')[1];
        // atob: giải mã base64 (chỉ hoạt động trên trình duyệt)
        const decoded = JSON.parse(atob(payload)); 
        return decoded.user_id; 
    } catch (e) {
        return null;
    }
}

// --- CÁC HÀM TÍCH HỢP SOA (GỌI CÁC DỊCH VỤ) ---

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