// script.js

// 1. CẤU HÌNH KẾT NỐI
const BASE_GATEWAY_URL = "http://127.0.0.1:8000"; 

// Khởi tạo Socket.IO kết nối tập trung tới API Gateway
let socket;
try {
    socket = io(BASE_GATEWAY_URL, {
        transports: ['websocket'], 
        upgrade: false,
        reconnection: true,
        reconnectionAttempts: 5,
        timeout: 10000
    });
    
    // Lắng nghe tin nhắn từ Server bắn về thông qua Gateway
    socket.on('receive_message', (data) => {
        const chatWrapper = document.getElementById('chatWrapper');
        if (chatWrapper && chatWrapper.style.display !== 'none') {
            const currentOrder = chatWrapper.getAttribute('data-current-order') || document.getElementById('currentChatOrderId')?.value;
            
            // Kiểm tra xem tin nhắn có thuộc về đơn hàng đang mở không
            if (parseInt(data.order_id) === parseInt(currentOrder)) {
                const myRole = getUserRole();
                const isMe = data.role === myRole;

                // Tránh lặp tin nhắn của chính mình vì đã append cục bộ khi gửi
                if (!isMe) {
                    appendMessageToUI(data);
                }
            }
        }
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
            `<a href="admin.html" class="bg-blue-600 text-white px-4 py-2 rounded-md font-semibold hover:bg-blue-700">⚙️ Quản trị</a>` : 
            `<a href="profile.html" class="bg-blue-600 text-white px-4 py-2 rounded-md font-semibold hover:bg-blue-700">👤 Hồ sơ</a>`;

        authGroup.innerHTML = `
            <div class="flex items-center gap-4">
                ${actionLink}
                <a href="#" onclick="handleLogout()" class="text-gray-600 hover:text-red-600 font-semibold">Đăng xuất</a>
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
    return localStorage.getItem('user_role');
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
        const finalOrderId = order.id;

        if (response.ok && finalOrderId) {
            window.location.href = `payment.html?orderId=${finalOrderId}&amount=${order.total_amount || amount}`;
        } else {
            alert("Lỗi hệ thống: " + (order.message || "Không nhận được ID đơn hàng"));
        }
    } catch (error) {
        console.error("Lỗi đặt hàng:", error);
    }
}

// --- 4. ADMIN: HẸN LỊCH & THÔNG BÁO TỰ ĐỘNG ---

function showScheduleForm(orderId) {
    const modal = document.getElementById('scheduleModal');
    if (modal) {
        document.getElementById('currentOrderId').value = orderId;
        modal.classList.remove('hidden'); 
        modal.style.display = 'flex';    
    }
}

function closeModal() {
    const modal = document.getElementById('scheduleModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}


// --- 5. LOGIC CHATBOX REAL-TIME ---

async function openChat(orderId, name) {
    const chatWrapper = document.getElementById('chatWrapper');
    const chatMessages = document.getElementById('chatMessages');
    const chatOrderIdInput = document.getElementById('currentChatOrderId'); 
    if (!chatWrapper || !chatMessages) return;

    chatWrapper.style.display = 'flex';
    const cleanOrderId = parseInt(orderId);
    chatWrapper.setAttribute('data-current-order', cleanOrderId);
    if (chatOrderIdInput) chatOrderIdInput.value = cleanOrderId;
    
    document.getElementById('chatWithUser').textContent = name;
    chatMessages.innerHTML = '<p class="text-center text-gray-400 text-xs py-4">Đang tải hội thoại...</p>';
    
    if (socket && socket.connected) {
        socket.emit('join', { order_id: cleanOrderId });
    }
    
    try {
        const res = await fetch(`${BASE_GATEWAY_URL}/chat/api/v1/chat/${cleanOrderId}`, { 
            headers: getAuthHeader() 
        });
        
        if (res.ok) {
            const messages = await res.json();
            chatMessages.innerHTML = ''; 
            if (!messages || messages.length === 0) {
                chatMessages.innerHTML = '<p class="text-center text-gray-300 text-xs py-4">Chưa có tin nhắn nào.</p>';
            } else {
                messages.forEach(msg => appendMessageToUI(msg));
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    } catch (e) { 
        console.error("Lỗi tải lịch sử chat:", e);
        chatMessages.innerHTML = '<p class="text-center text-red-500 text-xs py-4">Lỗi tải tin nhắn.</p>';
    }
}

function closeChat() {
    const chatWrapper = document.getElementById('chatWrapper');
    if (chatWrapper) chatWrapper.style.display = 'none';
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const chatWrapper = document.getElementById('chatWrapper');
    const orderId = chatWrapper.getAttribute('data-current-order') || document.getElementById('currentChatOrderId')?.value;
    const role = getUserRole();
    const name = (role === 'admin' ? "Quản trị viên" : (localStorage.getItem('user_name') || "Khách hàng"));
    
    if (!input.value.trim() || !orderId) return;

    const msgData = {
        order_id: parseInt(orderId),
        role: role,
        name: name,
        content: input.value,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    appendMessageToUI(msgData); // Optimistic UI

    if (socket && socket.connected) {
        socket.emit('send_message', msgData);
        input.value = '';
    } else {
        alert("Mất kết nối máy chủ Chat!");
    }
}

function appendMessageToUI(data) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const msgDiv = document.createElement('div');
    const myRole = getUserRole();
    
    const isSystem = data.role === 'system';
    const isMe = data.role === myRole;

    if (isSystem) {
        msgDiv.className = 'msg self-center bg-yellow-100 text-yellow-800 text-[11px] italic px-3 py-1 rounded-md my-1 max-w-[95%] text-center';
        msgDiv.style.alignSelf = 'center';
        msgDiv.innerHTML = data.content;
    } else {
        msgDiv.className = `msg ${isMe ? 'msg-admin bg-blue-600 text-white' : 'msg-customer bg-gray-200 text-gray-800'} p-3 rounded-lg max-w-[85%] text-sm mb-2 shadow-sm`;
        msgDiv.style.alignSelf = isMe ? 'flex-end' : 'flex-start';
        msgDiv.innerHTML = `<small class="block text-[10px] opacity-75 mb-1">${data.name} • ${data.time}</small><div>${data.content}</div>`;
    }
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- 6. DASHBOARD & PROFILE ---

async function loadCustomerOrders() {
    const orderTableBody = document.getElementById('user-orders-body');
    if (!orderTableBody) return;

    orderTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-10">Đang tải đơn hàng...</td></tr>';

    try {
        const res = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders`, { headers: getAuthHeader() });
        const orders = await res.json();

        if (!orders || orders.length === 0) {
            orderTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-10">Bạn chưa đặt chiếc xe nào.</td></tr>';
            return;
        }

        const rows = await Promise.all(orders.map(async (order) => {
            let carName = "Xe VinFast";
            try {
                if (order.items?.length > 0) {
                    const carRes = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars/${order.items[0].car_model_id}`);
                    if (carRes.ok) carName = (await carRes.json()).model_name;
                }
            } catch (e) {}

            return `
                <tr class="border-b hover:bg-gray-50">
                    <td class="p-4 text-gray-600">#${order.id}</td>
                    <td class="p-4 font-bold text-gray-800">${carName}</td>
                    <td class="p-4"><span class="status-tag ${order.status} px-3 py-1 rounded-full text-xs font-bold">${order.status}</span></td>
                    <td class="p-4">
                        <button class="bg-blue-100 text-blue-700 px-4 py-1 rounded-md hover:bg-blue-200 transition" onclick="openChat('${order.id}', 'Hỗ trợ VinFast')">💬 Nhắn tin</button>
                    </td>
                </tr>`;
        }));
        orderTableBody.innerHTML = rows.join('');
    } catch (e) {
        orderTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-10 text-red-500">Lỗi tải dữ liệu.</td></tr>';
    }
}

// --- 6. DASHBOARD CHUẨN (FIX LỖI 404 & BIỂU ĐỒ) ---
async function loadDashboard() {
    const dashboardBody = document.getElementById('orders-table-body');
    const totalRevElem = document.getElementById('total-revenue');
    if (!dashboardBody) return;

    try {
        // Lấy danh sách đơn hàng
        const orderRes = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders`, { headers: getAuthHeader() });
        const orders = await orderRes.json();

        // FIX URL CATALOG: Gọi đúng endpoint để Gateway điều hướng chuẩn
        const carRes = await fetch(`${BASE_GATEWAY_URL}/catalog/catalog/cars`, { headers: getAuthHeader() });
        const cars = await carRes.json();

        let totalRevenue = 0;
        let statusCounts = { 'Pending': 0, 'Paid': 0, 'Scheduled': 0, 'Confirmed': 0 };

        const rows = await Promise.all(orders.map(async (order) => {
            if (['Paid', 'Scheduled', 'Confirmed'].includes(order.status)) {
                totalRevenue += (order.total_amount || 0);
            }
            statusCounts[order.status] = (statusCounts[order.status] || 0) + 1;

            // Lấy tên khách hàng
            let userName = `Khách #${order.user_id}`;
            try {
                const userRes = await fetch(`${BASE_GATEWAY_URL}/users/api/v1/users/${order.user_id}`, { headers: getAuthHeader() });
                if (userRes.ok) {
                    const userData = await userRes.json();
                    userName = userData.name || userData.username || userName;
                }
            } catch (e) {}

            // Lấy tên xe từ mảng cars đã fetch (Dùng stock_quantity từ catalog service)
            let carName = "VinFast EV";
            const carInfo = cars.find(c => c.id === (order.items?.[0]?.car_model_id));
            if (carInfo) carName = carInfo.model_name;

            let actionBtn = `<button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 text-xs" onclick="showScheduleForm('${order.id}')">📅 Hẹn lịch</button>`;
            if (order.status === 'Scheduled' || order.status === 'Confirmed') {
                actionBtn = `<button class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 text-xs" onclick="openChat('${order.id}', '${userName}')">💬 Chat</button>`;
            }

            return `
                <tr class="border-b">
                    <td class="px-6 py-4 text-xs">#${order.id}</td>
                    <td class="px-6 py-4 font-bold text-gray-700">${userName}</td>
                    <td class="px-6 py-4 text-sm text-gray-600">${carName}</td>
                    <td class="px-6 py-4 text-blue-600 font-bold">${(order.total_amount || 0).toLocaleString()}đ</td>
                    <td class="px-6 py-4"><span class="status ${order.status}">${order.status}</span></td>
                    <td class="px-6 py-4">${actionBtn}</td>
                </tr>`;
        }));

        dashboardBody.innerHTML = rows.join('');
        if (totalRevElem) totalRevElem.textContent = totalRevenue.toLocaleString() + " VND";
        
        // Cập nhật biểu đồ Tồn kho và Trạng thái
        initCharts(statusCounts, cars);
    } catch (e) { 
        console.error("Dashboard Error:", e);
        dashboardBody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-red-500">Lỗi kết nối Dashboard. Hãy kiểm tra Console.</td></tr>';
    }
}

function initCharts(statusData, inventoryData) {
    if (typeof Chart === 'undefined') return;

    // Biểu đồ Doughnut trạng thái
    const ctxStatus = document.getElementById('orderStatusChart');
    if (ctxStatus) {
        const existingStatus = Chart.getChart('orderStatusChart');
        if (existingStatus) existingStatus.destroy();
        new Chart(ctxStatus, {
            type: 'doughnut',
            data: {
                labels: Object.keys(statusData),
                datasets: [{ data: Object.values(statusData), backgroundColor: ['#fff3cd', '#d1fae5', '#dbeafe', '#e0e7ff'] }]
            },
            options: { maintainAspectRatio: false }
        });
    }

    // Biểu đồ Bar tồn kho (Dùng stock_quantity)
    const ctxInv = document.getElementById('inventoryChart');
    if (ctxInv && inventoryData) {
        const existingInv = Chart.getChart('inventoryChart');
        if (existingInv) existingInv.destroy();
        new Chart(ctxInv, {
            type: 'bar',
            data: {
                labels: inventoryData.map(c => c.model_name),
                datasets: [{
                    label: 'Số lượng tồn',
                    data: inventoryData.map(c => c.stock_quantity || 0),
                    backgroundColor: '#1464F4'
                }]
            },
            options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
        });
    }
}

// --- FIX LỖI MODAL VÀ LUỒNG THỰC THI ---
async function submitSchedule() {
    const orderId = document.getElementById('currentOrderId').value;
    const address = document.getElementById('showroomAddress').value;
    const time = document.getElementById('appointmentTime').value;

    if (!time) return alert("Vui lòng chọn thời gian hẹn!");

    try {
        const res = await fetch(`${BASE_GATEWAY_URL}/orders/api/v1/orders/${orderId}/confirm`, {
            method: 'PUT',
            headers: getAuthHeader()
        });

        if (res.ok) {
            // Gửi thông báo chat (Try-catch riêng để nếu Chat lỗi vẫn đóng được Modal)
            try {
                await fetch(`${BASE_GATEWAY_URL}/chat/api/v1/chat/system_notify`, {
                    method: 'POST',
                    headers: getAuthHeader(),
                    body: JSON.stringify({
                        order_id: parseInt(orderId),
                        content: `📅 THÔNG BÁO: Admin đã xác nhận lịch hẹn tại ${address} lúc ${time.replace('T', ' ')}.`
                    })
                });
            } catch (e) { console.warn("Lỗi gửi thông báo Chat"); }

            alert("Xác nhận lịch hẹn thành công!");
            closeModal(); // Đảm bảo Modal ẩn đi
            loadDashboard(); // Cập nhật lại số liệu bảng
        }
    } catch (e) { alert("Lỗi kết nối khi gửi lịch hẹn!"); }
}

function closeModal() {
    const modal = document.getElementById('scheduleModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

function loadProfile() {
    const nameInput = document.getElementById('fullname');
    const emailInput = document.getElementById('email');
    if (nameInput) nameInput.value = localStorage.getItem('user_name') || "";
    if (emailInput) emailInput.value = localStorage.getItem('user_email') || "";
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
    updateHeaderUI();
    if (document.getElementById('orders-table-body')) loadDashboard();
    if (document.getElementById('user-orders-body')) loadCustomerOrders();
    if (document.getElementById('fullname')) loadProfile();
});