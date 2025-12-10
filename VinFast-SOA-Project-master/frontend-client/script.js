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

document.addEventListener("DOMContentLoaded", async function() {
    const loginLink = document.getElementById('login-link');
    const logoutLink = document.getElementById('logout-link');
    const registerBtn = document.querySelector('.header-actions .btn-primary[href="register.html"]'); 

    if (!loginLink) return;

    const token = localStorage.getItem('jwt_token');
    const userId = localStorage.getItem('user_id');

    if (token && userId) {
        // --- TRẠNG THÁI: ĐÃ ĐĂNG NHẬP ---
        if (registerBtn) registerBtn.style.display = 'none'; 
        if (logoutLink) logoutLink.style.display = 'inline-block';
        
        loginLink.href = "profile.html"; 
        loginLink.textContent = "👤 Tài khoản của tôi";

        try {
            const res = await fetch(`${BASE_GATEWAY_URL}/users/users/${userId}`);
            if (res.ok) {
                const user = await res.json();
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
            localStorage.removeItem('jwt_token');
            localStorage.removeItem('user_id');
            window.location.href = 'index.html';
        });
    }
});

// --- 3. CÁC HÀM HỖ TRỢ LẤY DỮ LIỆU ---

async function fetchUserName(userId) {
    try {
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


// --- 4. HÀM VẼ BIỂU ĐỒ (MỚI) ---

function renderCharts(orders, carList) {
    // 1. Dữ liệu Trạng thái Đơn hàng (Orders)
    const statusCounts = orders.reduce((acc, order) => {
        acc[order.status] = (acc[order.status] || 0) + 1;
        return acc;
    }, {});

    const statusLabels = Object.keys(statusCounts);
    const statusData = Object.values(statusCounts);
    const statusColors = statusLabels.map(status => {
        if (status === 'Confirmed') return '#4CAF50';
        if (status === 'Pending') return '#FFC107';
        if (status === 'Canceled') return '#F44336';
        return '#9E9E9E';
    });

    const orderStatusCtx = document.getElementById('orderStatusChart').getContext('2d');
    new Chart(orderStatusCtx, {
        type: 'pie',
        data: {
            labels: statusLabels,
            datasets: [{
                data: statusData,
                backgroundColor: statusColors,
            }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
    });

    // 2. Dữ liệu Tồn kho Sản phẩm (Catalog)
    // Lấy tồn kho của tất cả xe
    const inventoryLabels = carList.map(car => car.model_name);
    // Lưu ý: Tồn kho T2 (Catalog Service) chỉ lấy tổng từ DB, không phải từ API.
    // Vì bạn chưa có API Inventory Stats, ta sẽ tính tổng tạm thời bằng cách giả định.
    // Tạm thời, ta dùng giá trị base_price để tạo biểu đồ ví dụ.
    const inventoryData = carList.map(car => car.base_price); 
    
    // Nếu bạn đã có API /catalog/reports/inventory-stats, hãy gọi nó ở đây.
    
    const inventoryCtx = document.getElementById('inventoryChart').getContext('2d');
    new Chart(inventoryCtx, {
        type: 'bar',
        data: {
            labels: inventoryLabels,
            datasets: [{
                label: 'Giá niêm yết (triệu VND)', // Giả định
                data: inventoryData.map(price => price / 1000000), 
                backgroundColor: '#1464F4',
            }]
        },
        options: { 
            responsive: true,
            scales: { y: { beginAtZero: true } }
        }
    });
}


// --- 5. HÀM CHÍNH TẢI DASHBOARD (ĐÃ TÍCH HỢP BIỂU ĐỒ & KPI) ---

async function loadDashboard() {
    const dashboardBody = document.getElementById('orders-table-body');
    const statusMessage = document.getElementById('status-message');
    const totalRevenueDiv = document.getElementById('total-revenue');
    
    if (!dashboardBody) return;

    dashboardBody.innerHTML = '<tr><td colspan="5">Đang tải dữ liệu...</td></tr>';
    totalRevenueDiv.textContent = 'Đang tải...';
    statusMessage.innerHTML = '';
    
    let orders = [];
    let carList = [];
    let totalConfirmedRevenue = 0;

    try {
        // TẢI TẤT CẢ ĐƠN HÀNG (T3)
        const orderResponse = await fetch(`${BASE_GATEWAY_URL}/orders/orders`); 
        if (!orderResponse.ok) {
            statusMessage.innerHTML = `Lỗi Tải Đơn Hàng (T3): Server trả về ${orderResponse.status}.`;
            return;
        }
        orders = await orderResponse.json();
        
        // TẢI TẤT CẢ DANH MỤC XE (T2 - Cần cho cả bảng và biểu đồ Tồn kho)
        const catalogResponse = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars`); 
        if (catalogResponse.ok) {
            carList = await catalogResponse.json();
        }

    } catch (error) {
        statusMessage.innerHTML = `Lỗi Kết nối Gateway: Đảm bảo Docker (Gateway, T1, T2, T3) đang chạy.`;
        return;
    }
    
    dashboardBody.innerHTML = ''; 
    
    if (orders.length === 0) {
         dashboardBody.innerHTML = '<tr><td colspan="5">Chưa có đơn hàng nào được tạo thành công.</td></tr>';
    }

    // MAP dữ liệu xe vào một Dict để tra cứu nhanh hơn
    const carMap = carList.reduce((map, car) => {
        map[car.id] = car;
        return map;
    }, {});

    // Tích hợp và hiển thị BẢNG
    for (const order of orders) {
        const userName = await fetchUserName(order.user_id);
        
        let itemDetails = '';
        for (const item of order.items) {
            const car = carMap[item.car_model_id] || { model_name: `Xe ID ${item.car_model_id}` };
            const priceVND = item.unit_price.toLocaleString('vi-VN') + ' VND'; 

            itemDetails += `${car.model_name} (${item.quantity} chiếc, ${priceVND}/chiếc)<br>`;
        }
        
        // TÍNH TOÁN KPI DOANH THU
        if (order.status === 'Confirmed') {
            totalConfirmedRevenue += order.total_amount;
        }
        
        const row = dashboardBody.insertRow();
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${order.order_id}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${userName}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${itemDetails}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">${order.total_amount.toLocaleString('vi-VN')} VND</td>
            <td class="px-6 py-4 whitespace-nowrap"><span class="status ${order.status}">${order.status}</span></td>
        `;
    }
    
    // CẬP NHẬT KPI & BIỂU ĐỒ
    totalRevenueDiv.textContent = totalConfirmedRevenue.toLocaleString('vi-VN') + ' VND';
    renderCharts(orders, carList);
}