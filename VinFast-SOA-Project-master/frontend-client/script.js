// script.js

// 1. CẤU HÌNH KẾT NỐI
const BASE_GATEWAY_URL = "http://127.0.0.1:8000"; 

// Khởi tạo Socket.IO với cơ chế bọc lỗi an toàn
let socket;
try {
    // SỬA LỖI: Chỉ sử dụng 'websocket' và tắt 'polling' để tránh kẹt kết nối trình duyệt
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
            localStorage.setItem('jwt_token', data.access_token);
            localStorage.setItem('user_id', data.user_id);
            localStorage.setItem('user_role', data.role);
            
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
        
        const finalOrderId = order.id || order._id || (order.data && (order.data.id || order.data._id));

        if (response.ok && finalOrderId) {
            window.location.href = `payment.html?orderId=${finalOrderId}&amount=${order.total_amount || amount}`;
        } else {
            console.error("Phản hồi đơn hàng lỗi:", order);
            alert("Lỗi hệ thống: " + (order.message || "Không nhận được ID đơn hàng từ Server."));
        }
    } catch (error) {
        console.error("Lỗi đặt hàng:", error);
        alert("Lỗi kết nối dịch vụ đặt hàng!");
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

    try {
        await fetch(`${BASE_GATEWAY_URL}/chat/api/v1/chat/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, message: messageContent })
        });

        const res = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders/${orderId}/confirm`, {
            method: 'PUT',
            headers: getAuthHeader()
        });

        if (res.ok) {
            alert("Đã gửi lịch hẹn thành công!");
            location.reload(); 
        }
    } catch (e) {
        alert("Lỗi khi gửi lịch hẹn!");
    }
}

// --- 5. LOGIC CHATBOX REAL-TIME ---

function openChat(orderId, name) {
    const chatWrapper = document.getElementById('chatWrapper');
    if (chatWrapper) {
        chatWrapper.style.display = 'flex';
        chatWrapper.setAttribute('data-current-order', orderId);
        document.getElementById('chatWithUser').textContent = name;
        
        if (socket && socket.connected) {
            socket.emit('join', { order_id: orderId });
        }
        // FIX: Xóa sạch tin nhắn cũ trước khi tải mới để tránh lặp hoặc trắng
        document.getElementById('chatMessages').innerHTML = '';
        loadChatHistory(orderId);
    }
}

function closeChat() {
    document.getElementById('chatWrapper').style.display = 'none';
}

async function loadChatHistory(orderId) {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '<p style="text-align:center;font-size:10px;">Đang tải...</p>';
    
    try {
        const res = await fetch(`${BASE_GATEWAY_URL}/chat/api/v1/chat/${orderId}`, { headers: getAuthHeader() });
        const messages = await res.json();
        chatMessages.innerHTML = '';
        messages.forEach(msg => appendMessageToUI(msg));
        // Ép cuộn xuống cuối sau khi tải xong lịch sử
        setTimeout(() => { chatMessages.scrollTop = chatMessages.scrollHeight; }, 100);
    } catch (e) { 
        console.error("Lỗi tải lịch sử chat");
        chatMessages.innerHTML = '<p style="text-align:center;color:red;">Lỗi tải tin nhắn.</p>';
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const orderId = document.getElementById('chatWrapper').getAttribute('data-current-order');
    const role = getUserRole();
    const name = (role === 'admin' ? "Quản trị viên" : "Khách hàng");
    
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
        // FIX: Tự hiển thị tin nhắn của chính mình ngay lập tức để không bị trắng khung
        appendMessageToUI(msgData);
    } else {
        alert("Mất kết nối máy chủ Chat!");
    }
    input.value = '';
}

if (socket) {
    socket.on('receive_message', function(data) {
        const currentOrder = document.getElementById('chatWrapper').getAttribute('data-current-order');
        // Chỉ append nếu tin nhắn thuộc về đơn hàng đang mở
        if (parseInt(data.order_id) === parseInt(currentOrder)) {
            appendMessageToUI(data);
        }
    });
}

function appendMessageToUI(data) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `msg ${data.role === 'admin' ? 'msg-admin' : 'msg-customer'}`;
    msgDiv.innerHTML = `<strong>${data.name}:</strong><br>${data.content}`;
    
    chatMessages.appendChild(msgDiv);
    // Tự động cuộn xuống dưới cùng
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- 6. DASHBOARD ADMIN (MASHUP & CHARTS) ---

async function loadDashboard() {
    const dashboardBody = document.getElementById('orders-table-body');
    const totalRevElem = document.getElementById('total-revenue');
    if (!dashboardBody) return;

    try {
        const orderRes = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders`, { headers: getAuthHeader() });
        if (!orderRes.ok) throw new Error("Order Service disconnected");
        
        const orders = await orderRes.json();
        let totalRevenue = 0;
        let statusCounts = { 'Pending': 0, 'Paid': 0, 'Scheduled': 0, 'Confirmed': 0 };

        dashboardBody.innerHTML = '';
        
        const rows = await Promise.all(orders.map(async (order, index) => {
            const orderId = order.id || order._id || (index + 1);
            
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
            } catch (e) { console.warn("Lỗi lấy thông tin user"); }
            
            let actionBtn = "";
            if (['Paid', 'Confirmed', 'Pending'].includes(order.status)) {
                actionBtn = `<button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700" onclick="showScheduleForm('${orderId}')">✅ Hẹn lịch</button>`;
            } else if (order.status === 'Scheduled') {
                actionBtn = `<button class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700" onclick="openChat('${orderId}', '${userName}')">💬 Chat</button>`;
            } else {
                actionBtn = `<span class="text-gray-400 text-xs">N/A</span>`;
            }

            return `
                <tr>
                    <td class="px-6 py-4">#${orderId}</td>
                    <td class="px-6 py-4 font-bold text-gray-700">${userName}</td>
                    <td class="px-6 py-4">Xe điện VinFast</td>
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
        dashboardBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:red; padding:20px;">⚠️ Lỗi kết nối dịch vụ.</td></tr>';
    }
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
    if (document.getElementById('orders-table-body')) {
        loadDashboard();
    }
});