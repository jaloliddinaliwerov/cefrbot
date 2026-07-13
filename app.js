// Global Config
let API_URL = localStorage.getItem('api_url') || window.location.origin;
let adminToken = localStorage.getItem('admin_token') || '';
let chartInstance = null;

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    // Determine API URL fallback
    if (!localStorage.getItem('api_url') && !window.location.origin.includes('localhost') && !window.location.origin.includes('127.0.0.1')) {
        // If not running locally and not configured, default to current origin
        API_URL = window.location.origin;
    }
    
    document.getElementById('api-url-input').value = API_URL;

    // Parse URL params
    const urlParams = new URLSearchParams(window.location.search);
    const tokenParam = urlParams.get('token');
    if (tokenParam) {
        localStorage.setItem('admin_token', tokenParam);
        adminToken = tokenParam;
        window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
    }

    // Parse Hash Routing
    const hash = window.location.hash || '#dashboard';
    switchTab(hash.replace('#', ''));

    // Check Admin Login
    checkAdminStatus();
    
    // Set up default dynamic question row
    addQuestionRow();
});

// Settings Modal
function openSettings() {
    document.getElementById('settings-modal').classList.remove('hidden');
}
function closeSettings() {
    document.getElementById('settings-modal').classList.add('hidden');
}
function saveSettings() {
    const url = document.getElementById('api-url-input').value.trim().replace(/\/$/, "");
    localStorage.setItem('api_url', url);
    API_URL = url;
    closeSettings();
    alert("Sozlamalar saqlandi. API URL: " + API_URL);
    // Reload active tab
    const activeTab = document.querySelector('.active-nav').id.replace('nav-', '');
    switchTab(activeTab);
}

// Mobile Menu
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    menu.classList.toggle('hidden');
}

// Navigation Tabs
function switchTab(tabName) {
    // Update hash
    window.location.hash = tabName;

    // Hide all contents
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    // Show active content
    const activeTabEl = document.getElementById(`tab-${tabName}`);
    if (activeTabEl) activeTabEl.classList.remove('hidden');

    // Update Nav bar buttons styling
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active-nav'));
    const activeBtn = document.getElementById(`nav-${tabName}`);
    if (activeBtn) activeBtn.classList.add('active-nav');

    // Fetch tab-specific data
    if (tabName === 'dashboard') {
        const lastSearchedId = localStorage.getItem('last_searched_tg_id') || 123456789; // Default placeholder
        document.getElementById('stats-tg-id').value = lastSearchedId;
        loadDashboard(lastSearchedId);
    } else if (tabName === 'leaderboard') {
        loadLeaderboard();
    } else if (tabName === 'mock') {
        loadMockExams();
    } else if (tabName === 'admin') {
        checkAdminStatus();
    }
}

// Dashboard Statistics Loading
async function loadStatsByInput() {
    const tgId = document.getElementById('stats-tg-id').value.trim();
    if (!tgId) {
        alert("Iltimos, Telegram ID kiriting.");
        return;
    }
    localStorage.setItem('last_searched_tg_id', tgId);
    loadDashboard(tgId);
}

async function loadDashboard(tgId) {
    try {
        const response = await fetch(`${API_URL}/api/stats/${tgId}`);
        if (!response.ok) throw new Error("Foydalanuvchi topilmadi or API error");
        
        const data = await response.json();
        
        // Update user badge
        document.getElementById('user-avatar').innerText = data.user.first_name ? data.user.first_name[0].toUpperCase() : 'U';
        document.getElementById('user-name').innerText = data.user.first_name || 'Talaba';
        document.getElementById('user-streak-badge').innerText = `${data.user.streak || 0} kun streak`;
        document.getElementById('user-xp-badge').innerText = `${data.user.xp || 0} XP`;
        
        // Stats grid
        document.getElementById('stat-tests').innerText = `${data.stats.tests_completed} ta`;
        document.getElementById('stat-avg-test').innerText = `${data.stats.average_test_score.toFixed(1)}%`;
        
        document.getElementById('stat-writings').innerText = `${data.stats.writings_completed} ta`;
        document.getElementById('stat-avg-writing').innerText = `O'rtacha: ${data.stats.average_writing_score.toFixed(1)}/100`;
        
        document.getElementById('stat-speakings').innerText = `${data.stats.speakings_completed} ta`;
        document.getElementById('stat-avg-speaking').innerText = `O'rtacha: ${data.stats.average_speaking_score.toFixed(1)}/100`;

        // Render progress chart
        renderChart(data.stats);

        // Load achievements
        loadAchievements(data.achievements);

    } catch (err) {
        console.error(err);
        // Show placeholder message / demo mode
        alert(`Kiritilgan Telegram ID (${tgId}) bo'yicha profil topilmadi. Botni ishga tushirib /start bosing yoki boshqa ID kiriting.`);
    }
}

function renderChart(stats) {
    const ctx = document.getElementById('progressChart').getContext('2d');
    
    if (chartInstance) {
        chartInstance.destroy();
    }

    const data = {
        labels: ['Reading & Listening (%)', 'Writing Score (100)', 'Speaking Score (100)'],
        datasets: [{
            label: 'Natijalar',
            data: [stats.average_test_score, stats.average_writing_score, stats.average_speaking_score],
            backgroundColor: [
                'rgba(14, 165, 233, 0.2)',
                'rgba(99, 102, 241, 0.2)',
                'rgba(244, 63, 94, 0.2)'
            ],
            borderColor: [
                '#0ea5e9',
                '#6366f1',
                '#f43f5e'
            ],
            borderWidth: 2
        }]
    };

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function loadAchievements(unlockedAchievements) {
    const list = document.getElementById('achievements-list');
    list.innerHTML = '';

    const allAchievements = [
        { id: "first_test", name: "Birinchi Qadam", description: "Birinchi testni topshirdingiz!", icon: "🏆" },
        { id: "streak_3", name: "Faol O'quvchi", description: "3 kun ketma-ket kirish", icon: "🔥" },
        { id: "streak_7", name: "Chempion", description: "7 kun ketma-ket kirish", icon: "👑" },
        { id: "perfect_score", name: "A'lochi", description: "Testdan 100% ball", icon: "💯" },
        { id: "mock_master", name: "Mock Eksperti", description: "Birinchi Mock imtihonini topshirdingiz", icon: "🎓" },
        { id: "writing_pro", name: "Ijodkor", description: "Birinchi insho topshirildi", icon: "✍️" },
        { id: "speaking_pro", name: "Notiq", description: "Birinchi gapirish topshirildi", icon: "🗣️" }
    ];

    allAchievements.forEach(ach => {
        const isUnlocked = unlockedAchievements.some(ua => ua.id === ach.id);
        const cardClass = isUnlocked ? 'badge-unlocked' : 'badge-locked';
        
        list.innerHTML += `
            <div class="flex items-center gap-3 p-3 rounded-xl ${cardClass} transition">
                <div class="text-2xl">${ach.icon}</div>
                <div>
                    <h4 class="text-sm font-semibold">${ach.name}</h4>
                    <p class="text-xs text-slate-400">${ach.description}</p>
                </div>
            </div>
        `;
    });
}

// Leaderboard Loading
async function loadLeaderboard() {
    try {
        const response = await fetch(`${API_URL}/api/leaderboard`);
        const data = await response.json();
        
        const tbody = document.getElementById('leaderboard-body');
        tbody.innerHTML = '';

        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-slate-400 italic">Leaderboardda o'quvchilar yo'q.</td></tr>`;
            return;
        }

        const medal_emojis = {1: "🥇", 2: "🥈", 3: "🥉"};

        data.forEach((user, idx) => {
            const medal = medal_emojis[idx + 1] || ` ${idx + 1} `;
            tbody.innerHTML += `
                <tr class="hover:bg-slate-900/30 transition">
                    <td class="p-4 font-bold text-slate-350">${medal}</td>
                    <td class="p-4 font-semibold">${user.first_name || 'Foydalanuvchi'}</td>
                    <td class="p-4 text-center text-orange-400">${user.streak || 0} 🔥</td>
                    <td class="p-4 text-right font-bold text-brand-400">${user.xp} XP</td>
                </tr>
            `;
        });
    } catch (err) {
        console.error(err);
    }
}

// Mock Exams Loading
async function loadMockExams() {
    try {
        const response = await fetch(`${API_URL}/api/mock-exams`);
        const data = await response.json();
        
        const grid = document.getElementById('mock-list-grid');
        grid.innerHTML = '';

        if (data.length === 0) {
            grid.innerHTML = `<div class="col-span-full text-center text-slate-400 italic py-8">Hozircha sotuvda Mock Imtihonlar yo'q.</div>`;
            return;
        }

        data.forEach(mock => {
            grid.innerHTML += `
                <div class="glass-card p-6 flex flex-col justify-between h-64">
                    <div>
                        <div class="flex items-center justify-between">
                            <span class="bg-indigo-500/20 text-indigo-300 text-xs px-2.5 py-0.5 rounded-full border border-indigo-500/30">CEFR Mock</span>
                            <span class="text-brand-400 font-bold text-sm">${mock.price.toLocaleString()} UZS</span>
                        </div>
                        <h3 class="text-lg font-bold mt-4">${mock.title}</h3>
                        <ul class="mt-3 space-y-1.5 text-xs text-slate-400">
                            <li><i class="fa-solid fa-circle-check text-emerald-500 mr-2"></i>Reading & Listening: ${mock.questions_count} ta savol</li>
                            <li><i class="fa-solid fa-circle-check text-indigo-500 mr-2"></i>Writing Tasks: ${mock.writing_count} ta insho</li>
                            <li><i class="fa-solid fa-circle-check text-rose-500 mr-2"></i>Speaking Tasks: ${mock.speaking_count} ta savol</li>
                        </ul>
                    </div>
                    <button onclick="alert('Ushbu mock imtihonini boshlash uchun Telegram botga kiring!')" class="w-full btn-primary py-2 text-sm mt-4">Botda topshirish</button>
                </div>
            `;
        });
    } catch (err) {
        console.error(err);
    }
}

// ====== ADMIN PORTAL FUNCTIONS ======

function checkAdminStatus() {
    const loginBox = document.getElementById('admin-login-box');
    const dashboard = document.getElementById('admin-dashboard');
    
    if (adminToken && verifyAdminStatelessToken(adminToken)) {
        loginBox.classList.add('hidden');
        dashboard.classList.remove('hidden');
        loadAdminData();
    } else {
        loginBox.classList.remove('hidden');
        dashboard.classList.add('hidden');
    }
}

// Client side basic token validation to avoid useless API calls
function verifyAdminStatelessToken(token) {
    if (!token || !token.includes(':')) return false;
    const parts = token.split(':');
    return parts[0].length > 0 && parts[1].length === 16;
}

function loginAdmin() {
    const token = document.getElementById('admin-token-input').value.trim();
    if (!token) {
        alert("Iltimos token kiriting.");
        return;
    }
    localStorage.setItem('admin_token', token);
    adminToken = token;
    checkAdminStatus();
}

function logoutAdmin() {
    localStorage.removeItem('admin_token');
    adminToken = '';
    checkAdminStatus();
}

// Switch admin subtabs
function switchAdminSubTab(subName) {
    document.querySelectorAll('.admin-sub-content').forEach(el => el.classList.add('hidden'));
    document.getElementById(`admin-sub-${subName}`).classList.remove('hidden');

    document.querySelectorAll('.admin-sub-btn').forEach(el => el.classList.remove('active-admin-sub'));
    document.getElementById(`admin-sub-nav-${subName}`).classList.add('active-admin-sub');
}

function loadAdminData() {
    loadAdminQuestions();
    loadAdminTasks();
    loadAdminMocks();
}

// 1. Admin Questions (Reading / Listening)
async function loadAdminQuestions() {
    try {
        const response = await fetch(`${API_URL}/api/admin/questions`, {
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        if (!response.ok) throw new Error();
        const data = await response.json();
        
        const tbody = document.getElementById('admin-questions-tbody');
        tbody.innerHTML = '';

        data.forEach(q => {
            tbody.innerHTML += `
                <tr class="border-b border-slate-800 hover:bg-slate-900/20">
                    <td class="p-3 font-semibold text-slate-400">${q.id}</td>
                    <td class="p-3 text-slate-200 capitalize font-medium">${q.section}</td>
                    <td class="p-3 text-slate-200">Part ${q.part}</td>
                    <td class="p-3 text-slate-200">${q.title}</td>
                    <td class="p-3 text-center text-slate-300 font-bold">${q.questions_json.length} ta</td>
                    <td class="p-3 text-right">
                        <button onclick="deleteQuestion(${q.id})" class="text-red-400 hover:text-red-500 font-medium transition"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        });
        
        // Populate mock exams questions pickers
        populateQuestionsPickers(data);
    } catch (err) {
        console.error(err);
    }
}

async function deleteQuestion(id) {
    if (!confirm("Ushbu testni o'chirmoqchimisiz?")) return;
    try {
        const res = await fetch(`${API_URL}/api/admin/questions/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        if (res.ok) {
            alert("O'chirildi!");
            loadAdminQuestions();
        }
    } catch (err) {
        alert("Xatolik yuz berdi.");
    }
}

function toggleQuestionFields() {
    const sec = document.getElementById('q-section').value;
    const readingText = document.getElementById('reading-text-wrapper');
    const listeningAudio = document.getElementById('listening-audio-wrapper');
    
    if (sec === 'reading') {
        readingText.classList.remove('hidden');
        listeningAudio.classList.add('hidden');
    } else {
        readingText.classList.add('hidden');
        listeningAudio.classList.remove('hidden');
    }
}

function addQuestionRow() {
    const container = document.getElementById('questions-builder-container');
    const idx = container.children.length + 1;
    
    const row = document.createElement('div');
    row.className = "p-4 border border-slate-800 rounded-xl space-y-3 bg-slate-900/30 question-row";
    row.innerHTML = `
        <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <h5 class="text-xs font-bold text-slate-400">Savol #${idx}</h5>
            <button onclick="this.closest('.question-row').remove()" class="text-slate-400 hover:text-red-400 text-xs"><i class="fa-solid fa-times mr-1"></i>O'chirish</button>
        </div>
        <div class="space-y-2">
            <label class="text-xs text-slate-400">Savol matni</label>
            <input type="text" placeholder="Savolni yozing..." class="input-field py-1.5 text-xs row-q-text">
        </div>
        <div class="grid grid-cols-2 gap-2">
            <input type="text" placeholder="A variant" class="input-field py-1.5 text-xs row-opt-a">
            <input type="text" placeholder="B variant" class="input-field py-1.5 text-xs row-opt-b">
            <input type="text" placeholder="C variant" class="input-field py-1.5 text-xs row-opt-c">
            <input type="text" placeholder="D variant" class="input-field py-1.5 text-xs row-opt-d">
        </div>
        <div class="w-1/3">
            <label class="text-xs text-slate-400">To'g'ri javob</label>
            <select class="input-field py-1 text-xs row-answer">
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
            </select>
        </div>
    `;
    container.appendChild(row);
}

async function saveQuestion() {
    const section = document.getElementById('q-section').value;
    const part = parseInt(document.getElementById('q-part').value);
    const title = document.getElementById('q-title').value.trim();
    const text = document.getElementById('q-text').value.trim();
    const audioUrl = document.getElementById('q-audio-url').value.trim();
    
    if (!title) {
        alert("Sarlavhani kiriting.");
        return;
    }
    
    // Parse Dynamic Questions Rows
    const rows = document.querySelectorAll('.question-row');
    const questionsList = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const qText = row.querySelector('.row-q-text').value.trim();
        const optA = row.querySelector('.row-opt-a').value.trim();
        const optB = row.querySelector('.row-opt-b').value.trim();
        const optC = row.querySelector('.row-opt-c').value.trim();
        const optD = row.querySelector('.row-opt-d').value.trim();
        const answer = row.querySelector('.row-answer').value;
        
        if (!qText || !optA || !optB) {
            alert(`Savol #${i+1} ni to'liq to'ldiring (kamida A va B variantlari bo'lishi kerak).`);
            return;
        }
        
        questionsList.push({
            id: i + 1,
            q: qText,
            options: [`A: ${optA}`, `B: ${optB}`, `C: ${optC}`, `D: ${optD}`].filter(o => o.split(': ')[1]),
            answer: answer
        });
    }

    if (questionsList.length === 0) {
        alert("Kamida bitta savol qo'shing.");
        return;
    }

    const payload = {
        section,
        part,
        title,
        text: section === 'reading' ? text : null,
        audio_url: section === 'listening' ? audioUrl : null,
        questions_json: questionsList,
        is_mock: false
    };

    try {
        const response = await fetch(`${API_URL}/api/admin/questions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${adminToken}`
            },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            alert("Test muvaffaqiyatli saqlandi!");
            // Reset form
            document.getElementById('q-title').value = '';
            document.getElementById('q-text').value = '';
            document.getElementById('q-audio-url').value = '';
            document.getElementById('questions-builder-container').innerHTML = '';
            addQuestionRow();
            loadAdminQuestions();
        } else {
            const data = await response.json();
            alert("Xatolik: " + data.detail);
        }
    } catch (err) {
        alert("API ulanish xatosi.");
    }
}

// 2. Admin Writing / Speaking Tasks
async function loadAdminTasks() {
    try {
        const w_res = await fetch(`${API_URL}/api/admin/writing-tasks`, {
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        const writings = await w_res.json();
        
        const s_res = await fetch(`${API_URL}/api/admin/speaking-tasks`, {
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        const speakings = await s_res.json();

        // Populate lists
        const w_ul = document.getElementById('admin-writings-ul');
        w_ul.innerHTML = writings.length === 0 ? '<li class="text-slate-400 italic">Vazifalar yo'q.</li>' : '';
        writings.forEach(w => {
            w_ul.innerHTML += `
                <li class="flex items-center justify-between p-3 border border-slate-800 rounded-xl bg-slate-900/30">
                    <div>
                        <h4 class="font-bold text-sm">${w.title} (${w.level})</h4>
                        <p class="text-xs text-slate-400 truncate max-w-xs">${w.prompt}</p>
                    </div>
                    <button onclick="deleteTask('writing', ${w.id})" class="text-red-400 hover:text-red-500 transition"><i class="fa-solid fa-trash"></i></button>
                </li>
            `;
        });

        const s_ul = document.getElementById('admin-speakings-ul');
        s_ul.innerHTML = speakings.length === 0 ? '<li class="text-slate-400 italic">Vazifalar yo'q.</li>' : '';
        speakings.forEach(s => {
            s_ul.innerHTML += `
                <li class="flex items-center justify-between p-3 border border-slate-800 rounded-xl bg-slate-900/30">
                    <div>
                        <h4 class="font-bold text-sm">${s.title} (Part ${s.part} - ${s.level})</h4>
                        <p class="text-xs text-slate-400 truncate max-w-xs">${s.prompt}</p>
                    </div>
                    <button onclick="deleteTask('speaking', ${s.id})" class="text-red-400 hover:text-red-500 transition"><i class="fa-solid fa-trash"></i></button>
                </li>
            `;
        });
        
        // Populate mock exam pickers
        populateTasksPickers(writings, speakings);
        
    } catch (err) {
        console.error(err);
    }
}

async function deleteTask(type, id) {
    if (!confirm("Ushbu topshiriqni o'chirmoqchimisiz?")) return;
    try {
        const res = await fetch(`${API_URL}/api/admin/${type}-tasks/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        if (res.ok) {
            alert("O'chirildi!");
            loadAdminTasks();
        }
    } catch (err) {
        alert("Xatolik.");
    }
}

function toggleTaskFields() {
    const type = document.getElementById('task-type').value;
    const speakingWrapper = document.getElementById('speaking-part-wrapper');
    if (type === 'speaking') {
        speakingWrapper.classList.remove('hidden');
    } else {
        speakingWrapper.classList.add('hidden');
    }
}

async function saveTask() {
    const type = document.getElementById('task-type').value;
    const level = document.getElementById('task-level').value;
    const part = parseInt(document.getElementById('task-part').value);
    const title = document.getElementById('task-title').value.trim();
    const prompt = document.getElementById('task-prompt').value.trim();
    
    if (!title || !prompt) {
        alert("Sarlavha va promptni to'ldiring.");
        return;
    }

    const payload = type === 'speaking'
        ? { title, prompt, part, level, is_mock: false }
        : { title, prompt, level, is_mock: false };

    try {
        const response = await fetch(`${API_URL}/api/admin/${type}-tasks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${adminToken}`
            },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            alert("Topshiriq saqlandi!");
            document.getElementById('task-title').value = '';
            document.getElementById('task-prompt').value = '';
            loadAdminTasks();
        }
    } catch (err) {
        alert("Xatolik.");
    }
}

// 3. Admin Mock Exams
async function loadAdminMocks() {
    try {
        const res = await fetch(`${API_URL}/api/admin/mock-exams`, {
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        const mocks = await res.json();
        
        const tbody = document.getElementById('admin-mocks-tbody');
        tbody.innerHTML = '';

        mocks.forEach(m => {
            tbody.innerHTML += `
                <tr class="border-b border-slate-800 hover:bg-slate-900/20">
                    <td class="p-3 font-semibold text-slate-400">${m.id}</td>
                    <td class="p-3 text-slate-200 font-bold">${m.title}</td>
                    <td class="p-3 text-slate-200">${m.price.toLocaleString()} UZS</td>
                    <td class="p-3 text-slate-200">${m.questions_ids.length} ta</td>
                    <td class="p-3 text-slate-200">${m.writing_ids.length} ta</td>
                    <td class="p-3 text-slate-200">${m.speaking_ids.length} ta</td>
                    <td class="p-3 text-right">
                        <button onclick="deleteMock(${m.id})" class="text-red-400 hover:text-red-500 transition"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        });
    } catch (err) {
        console.error(err);
    }
}

async function deleteMock(id) {
    if (!confirm("Ushbu mock imtihonini o'chirmoqchimisiz?")) return;
    try {
        const res = await fetch(`${API_URL}/api/admin/mock-exams/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${adminToken}` }
        });
        if (res.ok) {
            alert("O'chirildi!");
            loadAdminMocks();
        }
    } catch (err) {
        alert("Xatolik.");
    }
}

// Populate multi-pickers in mock exam builder
function populateQuestionsPickers(questions) {
    const container = document.getElementById('mock-questions-picker');
    container.innerHTML = '';
    questions.forEach(q => {
        container.innerHTML += `
            <label class="flex items-center gap-2 text-xs text-slate-350 cursor-pointer hover:text-white">
                <input type="checkbox" value="${q.id}" class="mock-q-checkbox">
                <span>[${q.section.toUpperCase()} Part ${q.part}] ${q.title}</span>
            </label>
        `;
    });
}

function populateTasksPickers(writings, speakings) {
    const w_container = document.getElementById('mock-writings-picker');
    w_container.innerHTML = '';
    writings.forEach(w => {
        w_container.innerHTML += `
            <label class="flex items-center gap-2 text-xs text-slate-350 cursor-pointer hover:text-white">
                <input type="checkbox" value="${w.id}" class="mock-w-checkbox">
                <span>${w.title} (${w.level})</span>
            </label>
        `;
    });

    const s_container = document.getElementById('mock-speakings-picker');
    s_container.innerHTML = '';
    speakings.forEach(s => {
        s_container.innerHTML += `
            <label class="flex items-center gap-2 text-xs text-slate-350 cursor-pointer hover:text-white">
                <input type="checkbox" value="${s.id}" class="mock-s-checkbox">
                <span>${s.title} (Part ${s.part} - ${s.level})</span>
            </label>
        `;
    });
}

async function saveMockExam() {
    const title = document.getElementById('mock-title').value.trim();
    const price = parseInt(document.getElementById('mock-price').value) || 0;
    
    if (!title) {
        alert("Sarlavha yozing.");
        return;
    }

    // Selected questions
    const questions_ids = Array.from(document.querySelectorAll('.mock-q-checkbox:checked')).map(el => parseInt(el.value));
    const writing_ids = Array.from(document.querySelectorAll('.mock-w-checkbox:checked')).map(el => parseInt(el.value));
    const speaking_ids = Array.from(document.querySelectorAll('.mock-s-checkbox:checked')).map(el => parseInt(el.value));

    if (questions_ids.length === 0 && writing_ids.length === 0 && speaking_ids.length === 0) {
        alert("Kamida bitta topshiriq tanlang.");
        return;
    }

    const payload = {
        title,
        price,
        questions_ids,
        writing_ids,
        speaking_ids,
        active: true
    };

    try {
        const res = await fetch(`${API_URL}/api/admin/mock-exams`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${adminToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert("Mock Imtihoni muvaffaqiyatli yaratildi!");
            document.getElementById('mock-title').value = '';
            document.getElementById('mock-price').value = '30000';
            // Uncheck all boxes
            document.querySelectorAll('.mock-q-checkbox, .mock-w-checkbox, .mock-s-checkbox').forEach(el => el.checked = false);
            loadAdminMocks();
        }
    } catch (err) {
        alert("Xatolik.");
    }
}
