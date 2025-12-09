// script.js (Phần này bổ sung thêm logic ChartJS và tính KPIs)

// BASE_GATEWAY_URL là cổng của API Gateway (T4), chạy trên cổng 8000
const BASE_GATEWAY_URL = "http://127.0.0.1:8000"; 

// --- CÁC HÀM XỬ LÝ PHIÊN (SESSION) ---

function saveToken(token) {
    localStorage.setItem('jwt_token', token);
}

function getAuthHeader() {
    const token = localStorage.getItem('jwt_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function getUserIdFromToken(token) {
    try {
        const payload = token.split('.')[1];
        const decoded = JSON.parse(atob(payload)); 
        return decoded.user_id; 
    } catch (e) {
        return null;
    }
}

// --- HÀM TÍCH HỢP SOA (GỌI CÁC DỊCH VỤ) ---

async function fetchUserName(userId) {
    try {
        // GỌI T1 QUA GATEWAY
        const response = await fetch(`${BASE_GATEWAY_URL}/users/users/${userId}`); 
        if (response.ok) {
            const user = await response.json();
            return user.name || `User ID ${userId}`;
        }
        return `User ID ${userId} (Lỗi T1)`; 
    } catch (error) {
        return `Lỗi Kết nối T1`;
    }
}

// Hàm này được sử dụng trong các file HTML khác (index.html, car_detail.html)
async function fetchCarModelName(carId) {
    try {
        // GỌI T2 QUA GATEWAY
        const response = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars/${carId}`); 
        if (response.ok) {
            const car = await response.json();
            return car.model_name || `Car ID ${carId}`;
        }
        return `Car ID ${carId} (Lỗi T2)`;
    } catch (error) {
        return `Lỗi Kết nối T2`;
    }
}


// --- HÀM VẼ BIỂU ĐỒ (CHART.JS) ---

// Hàm vẽ Bar Chart Tồn kho (T2 Data)
function renderBarChart(elementId, labels, data, label) {
    const ctx = document.getElementById(elementId).getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: '#0070c0', 
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });
}

// Hàm vẽ Doughnut Chart Trạng thái (T3 Data)
function renderDoughnutChart(elementId, labels, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: ['#4CAF50', '#FF9800', '#F44336']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });
}

// --- LOGIC FETCH VÀ RENDER CHÍNH (CẤP L2) ---
// Hàm này là hàm khởi tạo chính, được gọi sau khi DOMContentLoaded trong admin.html
async function fetchAllDataAndRender() {
    try {
        // Fetch dữ liệu cần thiết từ T3 và T2 qua Gateway
        const orderResponse = await fetch(`${BASE_GATEWAY_URL}/orders/orders`);
        const catalogResponse = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars`);

        if (!orderResponse.ok || !catalogResponse.ok) {
            throw new Error("Lỗi tải dữ liệu từ Back-end.");
        }

        const orders = await orderResponse.json();
        const cars = await catalogResponse.json();
        
        // Mở rộng dữ liệu xe thành Map để tra cứu nhanh (Lookup)
        const carMap = new Map(cars.map(car => [car.id, car]));

        // 1. Logic Tính toán và KPIs (Cấp 3)
        let statusCounts = { Confirmed: 0, Pending: 0, Failed: 0 };
        let totalRevenue = 0;

        const detailedOrders = await Promise.all(orders.map(async order => {
            const userName = await fetchUserName(order.user_id);
            
            // Phân loại trạng thái và tính tổng doanh thu
            if (order.status === 'Confirmed') {
                statusCounts.Confirmed++;
                totalRevenue += order.total_amount;
            } else if (order.status === 'Pending') {
                statusCounts.Pending++;
            } else {
                statusCounts.Failed++; 
            }

            let itemDetails = '';
            order.items.forEach(item => {
                const car = carMap.get(item.car_model_id);
                // Tạo đối tượng car tạm thời để có thể truy cập inventory_HN/HCM
                const carData = car || { model_name: `Car ID ${item.car_model_id}`, inventory_HN: 0, inventory_HCM: 0 };
                
                const carName = carData.model_name;
                const priceVND = item.unit_price.toLocaleString('vi-VN');
                itemDetails += `${carName} (${item.quantity} chiếc, ${priceVND} VND/chiếc)<br>`;
            });

            return { ...order, userName, itemDetails };
        }));

        // 2. Render KPIs và Biểu đồ (Cấp 3 & 4)
        document.getElementById('total-revenue').textContent = totalRevenue.toLocaleString('vi-VN') + ' VND';
        renderOrderTable(detailedOrders);
        
        // Truyền statusCounts
        renderOrderStatusChart(statusCounts); 
        // Truyền dữ liệu xe đã fetch
        renderInventoryChart(cars); 

    } catch (error) {
        document.getElementById('status-message').textContent = `Lỗi tải dữ liệu: ${error.message}. Kiểm tra 4 dịch vụ (5001-5003, 8000).`;
    }
}

// Hàm render bảng (Cấp 2)
function renderOrderTable(orders) {
    const tbody = document.getElementById('orders-table-body');
    tbody.innerHTML = '';
    if (orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-4 text-center text-gray-500">Chưa có đơn hàng nào.</td></tr>';
        return;
    }
    orders.forEach(order => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">${order.order_id}</td>
            <td class="px-6 py-4 whitespace-nowrap">${order.userName}</td>
            <td class="px-6 py-4">${order.itemDetails}</td>
            <td class="px-6 py-4 whitespace-nowrap font-semibold">${order.total_amount.toLocaleString('vi-VN')} VND</td>
            <td class="px-6 py-4 whitespace-nowrap"><span class="status ${order.status}">${order.status}</span></td>
        `;
    });
}

// Hàm render Bar Chart (Tồn kho) - Dữ liệu T2
function renderInventoryChart(cars) {
    const labels = cars.map(c => c.model_name);
    // Tính tổng tồn kho (ví dụ: HN + HCM)
    const data = cars.map(c => (c.inventory_HN || 0) + (c.inventory_HCM || 0)); 
    
    const ctx = document.getElementById('inventoryChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Tổng Tồn Kho Hiện Tại',
                data: data,
                backgroundColor: '#0070c0', 
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });
}

// Hàm render Doughnut Chart Trạng thái (T3 Data)
function renderOrderStatusChart(statusCounts) {
    const statusLabels = ['Thành công (Confirmed)', 'Đang chờ (Pending)', 'Thất bại/Hủy (Failed)'];
    const statusData = [statusCounts.Confirmed, statusCounts.Pending, statusCounts.Failed];
    
    const ctx = document.getElementById('orderStatusChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: statusLabels,
            datasets: [{
                data: statusData,
                backgroundColor: ['#4CAF50', '#FF9800', '#F44336']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });
}


document.addEventListener('DOMContentLoaded', fetchAllDataAndRender);