// script.js

// 1. CẤU HÌNH KẾT NỐI
const BASE_GATEWAY_URL = "http://127.0.0.1:8000"; 

// Khởi tạo Socket.IO với cơ chế bọc lỗi an toàn
let socket;
try {
    socket = io(BASE_GATEWAY_URL, {
        transports: ['websocket'], 
        upgrade: false,
        reconnection: true,
        reconnectionAttempts: 5,
        timeout: 10000
    });
} catch (e) {
    console.error("Socket.IO không thể khởi tạo:", e);
}

// --- 2. XỬ LÝ TOKEN & XÁC THỰC ---

function getAuthHeader() {
    const token = localStorage.getItem('jwt_token');
    return token ? { 
        'Authorization': `Bearer ${token}`, 
        'Content-Type': 'application/json' 
    } : { 
        'Content-Type': 'application/json' 
    };
}

function updateHeaderUI() {
    const authGroup = document.getElementById('auth-group');
    if (!authGroup) return;

    const token = localStorage.getItem('jwt_token');
    const role = localStorage.getItem('user_role');

    if (token) {
        let actionLink = (role === 'admin') ? 
            `<a href="admin.html" class="btn-primary">⚙️ Quản trị</a>` : 
            `<a href="profile.html" class="btn-primary">👤 Hồ sơ</a>`;

        authGroup.innerHTML = `
            <div class="header-actions">
                ${actionLink}
                <a href="#" onclick="handleLogout()" class="btn-login">Đăng xuất</a>
            </div>
        `;
    }
}

function handleLogout() {
    localStorage.clear();
    alert("Đã đăng xuất thành công!");
    window.location.href = 'index.html';
}

async function handleLogin(email, password) {
    const loginMsg = document.getElementById('login-msg');
    try {
        const response = await fetch(`${BASE_GATEWAY_URL}/users/api/v1/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            // SỬA LỖI: Xóa sạch bộ nhớ cũ để tránh rác dữ liệu từ tài khoản trước
            localStorage.clear(); 

            localStorage.setItem('jwt_token', data.access_token);
            localStorage.setItem('user_id', data.user_id);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('user_name', data.name || "Khách hàng"); 
            localStorage.setItem('user_email', email);
            
            alert("Đăng nhập thành công!");
            window.location.href = (data.role === 'admin') ? 'admin.html' : 'index.html';
        } else {
            if(loginMsg) loginMsg.textContent = "❌ " + (data.message || "Sai tài khoản hoặc mật khẩu");
        }
    } catch (error) {
        console.error("Login error:", error);
        if(loginMsg) loginMsg.textContent = "❌ Lỗi kết nối đến Server!";
    }
}

function getUserRole() {
    const token = localStorage.getItem('jwt_token');
    if (!token) return null;
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.role; 
    } catch (e) { return null; }
}

// --- 3. LUỒNG ĐẶT CỌC & THANH TOÁN (CUSTOMER) ---

async function handleDeposit(carId, amount) {
    if (!localStorage.getItem('jwt_token')) {
        alert("Vui lòng đăng nhập để thực hiện đặt cọc!");
        window.location.href = 'login.html';
        return;
    }

    try {
        const response = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders`, {
            method: 'POST',
            headers: getAuthHeader(),
            body: JSON.stringify({ items: [{ car_id: carId, quantity: 1 }] })
        });

        const order = await response.json();
        const finalOrderId = order.id || order._id;

        if (response.ok && finalOrderId) {
            window.location.href = `payment.html?orderId=${finalOrderId}&amount=${order.total_amount || amount}`;
        } else {
            alert("Lỗi hệ thống: " + (order.message || "Không nhận được ID đơn hàng"));
        }
    } catch (error) {
        console.error("Lỗi đặt hàng:", error);
    }
}

// --- 4. ADMIN: HẸN LỊCH & THÔNG BÁO ---

function showScheduleForm(orderId) {
    const modal = document.getElementById('scheduleModal');
    if (modal) {
        document.getElementById('currentOrderId').value = orderId;
        modal.classList.remove('hidden'); 
        modal.style.display = 'block';    
    }
}

async function submitSchedule() {
    const orderId = document.getElementById('currentOrderId').value;
    const address = document.getElementById('showroomAddress').value;
    const time = document.getElementById('appointmentTime').value;

    if(!time) return alert("Vui lòng chọn thời gian hẹn!");

    const messageContent = `✨ THÔNG BÁO LỊCH HẸN ✨\n📍 Địa điểm: ${address}\n⏰ Thời gian: ${new Date(time).toLocaleString('vi-VN')}`;

    const msgData = {
        order_id: parseInt(orderId),
        role: 'admin',
        name: "Hệ thống VinFast",
        content: messageContent,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    try {
        // BƯỚC 1: LƯU TIN NHẮN VÀO DATABASE QUA API
        await fetch(`${BASE_GATEWAY_URL}/chat/api/v1/chat/send`, { 
            method: 'POST',
            headers: getAuthHeader(),
            body: JSON.stringify(msgData)
        });

        // BƯỚC 2: GỬI QUA SOCKET ĐỂ HIỆN THỊ REAL-TIME
        if (socket && socket.connected) {
            socket.emit('send_message', msgData);
        }

        // BƯỚC 3: CẬP NHẬT TRẠNG THÁI ĐƠN HÀNG SANG "SCHEDULED"
        const res = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders/${orderId}/confirm`, {
            method: 'PUT',
            headers: getAuthHeader()
        });

        if (res.ok) {
            alert("Đã gửi lịch hẹn và lưu vào lịch sử thành công!");
            const currentChatOrder = document.getElementById('chatWrapper').getAttribute('data-current-order');
            if (parseInt(currentChatOrder) === parseInt(orderId)) {
                appendMessageToUI(msgData);
            }
            location.reload(); 
        }
    } catch (e) {
        console.error("Lỗi submitSchedule:", e);
        alert("Lỗi khi gửi lịch hẹn!");
    }
}

// --- 5. LOGIC CHATBOX REAL-TIME ---

async function openChat(orderId, name) {
    const chatWrapper = document.getElementById('chatWrapper');
    if (!chatWrapper) return;

    chatWrapper.style.display = 'flex';
    const cleanOrderId = parseInt(orderId);
    chatWrapper.setAttribute('data-current-order', cleanOrderId);
    document.getElementById('chatWithUser').textContent = name;
    
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '<p style="text-align:center;font-size:10px;color:#999;">Đang tải hội thoại...</p>';
    
    if (socket && socket.connected) {
        socket.emit('join', { order_id: cleanOrderId });
    }
    
    try {
        const res = await fetch(`${BASE_GATEWAY_URL}/chat/api/v1/chat/${cleanOrderId}`, { 
            headers: getAuthHeader() 
        });
        
        if (!res.ok) throw new Error("Không thể kết nối API Chat");
        
        const messages = await res.json();
        chatMessages.innerHTML = ''; 
        
        if (!messages || messages.length === 0) {
            chatMessages.innerHTML = '<p style="text-align:center;font-size:10px;color:#ccc;">Chưa có tin nhắn nào.</p>';
        } else {
            messages.forEach(msg => appendMessageToUI(msg));
        }
        
        setTimeout(() => { 
            chatMessages.scrollTop = chatMessages.scrollHeight; 
        }, 50);

    } catch (e) { 
        console.error("Lỗi tải lịch sử chat:", e);
        chatMessages.innerHTML = '<p style="text-align:center;color:red;font-size:10px;">Lỗi tải lịch sử trò chuyện.</p>';
    }
}

function closeChat() {
    const chatWrapper = document.getElementById('chatWrapper');
    if (chatWrapper) chatWrapper.style.display = 'none';
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const chatWrapper = document.getElementById('chatWrapper');
    const orderId = chatWrapper.getAttribute('data-current-order');
    const role = getUserRole();
    const name = (role === 'admin' ? "Quản trị viên" : (localStorage.getItem('user_name') || "Khách hàng"));
    
    if (!input.value.trim()) return;

    const msgData = {
        order_id: parseInt(orderId),
        role: role,
        name: name,
        content: input.value,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    if (socket && socket.connected) {
        socket.emit('send_message', msgData);
        appendMessageToUI(msgData);
        input.value = '';
    } else {
        alert("Mất kết nối máy chủ Chat!");
    }
}

if (socket) {
    socket.on('receive_message', function(data) {
        const chatWrapper = document.getElementById('chatWrapper');
        if (chatWrapper && chatWrapper.style.display !== 'none') {
            const currentOrder = chatWrapper.getAttribute('data-current-order');
            if (parseInt(data.order_id) === parseInt(currentOrder)) {
                // Chỉ vẽ nếu là tin nhắn từ người khác gửi đến (để tránh lặp tin nhắn của chính mình)
                if (data.role !== getUserRole()) {
                    appendMessageToUI(data);
                }
            }
        }
    });
}

function appendMessageToUI(data) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `msg ${data.role === 'admin' ? 'msg-admin' : 'msg-customer'}`;
    msgDiv.innerHTML = `<strong>${data.name} (${data.time}):</strong><br>${data.content}`;
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- 6. DASHBOARD & PROFILE (CUSTOMER/ADMIN) ---

async function loadCustomerOrders() {
    const orderTableBody = document.getElementById('user-orders-body');
    if (!orderTableBody) return;

    // BƯỚC 1: Reset bảng về trạng thái đang tải để xóa dữ liệu cũ
    orderTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;">Đang tải danh sách đơn hàng của bạn...</td></tr>';

    try {
        const res = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders`, { 
            headers: getAuthHeader() 
        });

        if (res.status === 401) {
            orderTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:orange;">Vui lòng đăng nhập lại.</td></tr>';
            return;
        }

        const orders = await res.json();

        // BƯỚC 2: Nếu không có đơn hàng (tài khoản mới)
        if (!orders || orders.length === 0) {
            orderTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;">Bạn chưa có đơn hàng nào.</td></tr>';
            return;
        }

        const rows = await Promise.all(orders.map(async (order) => {
            let carName = "Xe VinFast";
            try {
                if (order.items && order.items.length > 0) {
                    const carId = order.items[0].car_model_id;
                    const catRes = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars/${carId}`);
                    if (catRes.ok) {
                        const carData = await catRes.json();
                        carName = carData.model_name;
                    }
                }
            } catch (e) { console.warn("Lỗi lấy tên xe"); }

            return `
                <tr>
                    <td>#${order.id}</td>
                    <td><strong>${carName}</strong></td>
                    <td><span class="status-tag ${order.status}">${order.status}</span></td>
                    <td>
                        <button class="btn-chat" onclick="openChat('${order.id}', 'Hỗ trợ VinFast')">💬 Nhắn tin</button>
                    </td>
                </tr>`;
        }));

        orderTableBody.innerHTML = rows.join('');

    } catch (e) {
        console.error("Lỗi tải đơn hàng:", e);
        orderTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:red;padding:20px;">⚠️ Lỗi tải dữ liệu.</td></tr>';
    }
}

async function loadDashboard() {
    const dashboardBody = document.getElementById('orders-table-body');
    const totalRevElem = document.getElementById('total-revenue');
    if (!dashboardBody) return;

    try {
        const orderRes = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders`, { headers: getAuthHeader() });
        const orders = await orderRes.json();
        let totalRevenue = 0;
        let statusCounts = { 'Pending': 0, 'Paid': 0, 'Scheduled': 0, 'Confirmed': 0 };

        dashboardBody.innerHTML = '';
        
        const rows = await Promise.all(orders.map(async (order) => {
            const orderId = order.id;
            if (['Paid', 'Scheduled', 'Confirmed'].includes(order.status)) {
                totalRevenue += (order.total_amount || 0);
            }
            statusCounts[order.status] = (statusCounts[order.status] || 0) + 1;

            let userName = `Người dùng #${order.user_id}`;
            try {
                const userRes = await fetch(`${BASE_GATEWAY_URL}/users/api/v1/users/${order.user_id}`, { headers: getAuthHeader() });
                if (userRes.ok) {
                    const user = await userRes.json();
                    userName = user.name || userName;
                }
            } catch (e) { console.warn("Lỗi user"); }

            let carName = "Đang tải...";
            try {
                if (order.items && order.items.length > 0) {
                    const carId = order.items[0].car_model_id;
                    const catRes = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars/${carId}`);
                    if (catRes.ok) {
                        const carData = await catRes.json();
                        carName = carData.model_name;
                    }
                }
            } catch (e) { carName = "Xe VinFast"; }
            
            let actionBtn = "";
            if (['Paid', 'Confirmed', 'Pending'].includes(order.status)) {
                actionBtn = `<button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700" onclick="showScheduleForm('${orderId}')">✅ Hẹn lịch</button>`;
            } else if (order.status === 'Scheduled') {
                actionBtn = `<button class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700" onclick="openChat('${orderId}', '${userName}')">💬 Chat</button>`;
            }

            return `
                <tr>
                    <td class="px-6 py-4">#${orderId}</td>
                    <td class="px-6 py-4 font-bold text-gray-700">${userName}</td>
                    <td class="px-6 py-4 text-sm text-gray-600">${carName}</td>
                    <td class="px-6 py-4 text-blue-600 font-bold">${(order.total_amount || 0).toLocaleString()} VND</td>
                    <td class="px-6 py-4"><span class="status ${order.status}">${order.status}</span></td>
                    <td class="px-6 py-4">${actionBtn}</td>
                </tr>`;
        }));

        dashboardBody.innerHTML = rows.join('');
        if (totalRevElem) totalRevElem.textContent = totalRevenue.toLocaleString() + " VND";
        initCharts(statusCounts);
    } catch (e) { 
        console.error("Lỗi Dashboard:", e); 
        dashboardBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:red;">⚠️ Lỗi kết nối.</td></tr>';
    }
}

function loadProfile() {
    const nameInput = document.getElementById('fullname');
    const emailInput = document.getElementById('email');
    if (!nameInput || !emailInput) return;

    nameInput.value = localStorage.getItem('user_name') || "";
    emailInput.value = localStorage.getItem('user_email') || "";
}

function initCharts(statusData) {
    ['orderStatusChart', 'inventoryChart'].forEach(id => {
        const existingChart = Chart.getChart(id);
        if (existingChart) existingChart.destroy();
    });

    const ctxStatus = document.getElementById('orderStatusChart');
    if (ctxStatus) {
        new Chart(ctxStatus, {
            type: 'doughnut',
            data: {
                labels: Object.keys(statusData),
                datasets: [{
                    data: Object.values(statusData),
                    backgroundColor: ['#fff3cd', '#d1fae5', '#dbeafe', '#fef3c7']
                }]
            },
            options: { maintainAspectRatio: false }
        });
    }

    const ctxInv = document.getElementById('inventoryChart');
    if (ctxInv) {
        new Chart(ctxInv, {
            type: 'bar',
            data: {
                labels: ['VF 8', 'VF 9', 'VF 7'],
                datasets: [{
                    label: 'Sẵn có',
                    data: [12, 5, 18],
                    backgroundColor: '#1464F4'
                }]
            },
            options: { maintainAspectRatio: false }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateHeaderUI();
    if (document.getElementById('orders-table-body')) loadDashboard();
    if (document.getElementById('user-orders-body')) loadCustomerOrders();
    if (document.getElementById('fullname')) loadProfile();
});