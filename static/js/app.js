// LumiSafe Client-side Application Logic

let mapInstance = null;
let markersLayer = null;
let cachedPoles = [];
let cachedComplaints = [];

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    await checkDatabaseStatus();
    await loadKPIs();
    await loadPoles();
    await loadComplaints();
    await loadCitizens();
    await loadMedia();
    await loadWorkOrders();
    await loadDivisions();
    await loadWards();
    await loadOfficials();
    initMap();
}

// -------------------------------------------------------------
// UI Navigation & Modals
// -------------------------------------------------------------
function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active-tab'));

    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) {
        targetTab.classList.remove('hidden');
    }

    // Highlight button
    event.currentTarget?.classList.add('active-tab');

    if (tabName === 'dashboard' || tabName === 'poles') {
        setTimeout(() => {
            if (mapInstance) mapInstance.invalidateSize();
        }, 150);
    }
}

function openModal(id) {
    document.getElementById(id)?.classList.remove('hidden');
}

function closeModal(id) {
    document.getElementById(id)?.classList.add('hidden');
}

function openReportComplaintModal(poleName = null) {
    openModal('modal-report-complaint');
    if (poleName) {
        const input = document.getElementById('complaint-pole-number');
        if (input) input.value = poleName;
        document.getElementById('complaint-issue').value = "Bulb Failure";
    }
}

function openAddPoleModal() {
    openModal('modal-add-pole');
}

function openAddCitizenModal() {
    openModal('modal-add-citizen');
}

function openAddWorkOrderModal() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('wo-date').value = today;
    openModal('modal-add-workorder');
}

function openAddMediaModal() {
    const select = document.getElementById('media-complaint-id');
    select.innerHTML = '';
    cachedComplaints.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.complaint_id;
        opt.textContent = `#${c.complaint_id} - ${c.issue_type} (${c.status})`;
        select.appendChild(opt);
    });
    openModal('modal-add-media');
}

function openAddDivisionModal() { openModal('modal-add-division'); }
function openAddWardModal() { openModal('modal-add-ward'); }
function openAddOfficialModal() { openModal('modal-add-official'); }

// Toast Notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const colors = {
        success: 'bg-emerald-600 text-white border-emerald-400',
        error: 'bg-red-600 text-white border-red-400',
        info: 'bg-blue-600 text-white border-blue-400',
        warning: 'bg-amber-600 text-slate-950 font-bold border-amber-300'
    };
    toast.className = `px-4 py-3 rounded-lg shadow-2xl border text-xs flex items-center gap-2 transform transition-all duration-300 pointer-events-auto ${colors[type] || colors.info}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

// -------------------------------------------------------------
// Database Status (Backend connected)
// -------------------------------------------------------------
async function checkDatabaseStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        const pillText = document.getElementById('db-status-text');
        const pillDot = document.getElementById('db-status-dot');

        if (pillText && pillDot) {
            if (data.active_driver === 'mysql' && data.mysql_live) {
                pillText.textContent = `MySQL Live (${data.mysql_db})`;
                pillDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
            } else {
                pillText.textContent = `SQLite Mirror (MySQL Offline/Locked)`;
                pillDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
            }
        }
    } catch (e) {
        console.error('Status check error:', e);
    }
}

// -------------------------------------------------------------
// KPIs & Dashboard
// -------------------------------------------------------------
async function loadKPIs() {
    try {
        const res = await fetch('/api/kpis');
        const json = await res.json();
        if (json.success) {
            const d = json.data;
            document.getElementById('kpi-total-poles').textContent = d.total_poles;
            document.getElementById('kpi-solar-poles').textContent = d.solar_poles;
            document.getElementById('kpi-elec-poles').textContent = d.electrical_poles;
            document.getElementById('kpi-risk-poles').textContent = d.high_risk_poles;
            document.getElementById('kpi-open-complaints').textContent = d.open_complaints;
            document.getElementById('kpi-progress-complaints').textContent = d.in_progress_complaints;
            document.getElementById('kpi-resolved-complaints').textContent = d.resolved_complaints;
            document.getElementById('kpi-pending-wo').textContent = d.pending_work_orders;
            document.getElementById('kpi-total-budget').textContent = `₹${d.total_budget.toLocaleString()}`;
        }
    } catch (e) {
        console.error('KPI load error:', e);
    }
}

// -------------------------------------------------------------
// GIS Map & Light Poles
// -------------------------------------------------------------
function initMap() {
    if (mapInstance) return;
    const defaultCenter = [12.935, 77.64]; // Bangalore
    mapInstance = L.map('map').setView(defaultCenter, 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(mapInstance);

    markersLayer = L.layerGroup().addTo(mapInstance);
    renderMapMarkers();
}

function renderMap() {
    if (!mapInstance) return;
    mapInstance.setView([12.935, 77.64], 13);
    renderMapMarkers();
}

function renderMapMarkers() {
    if (!markersLayer) return;
    markersLayer.clearLayers();

    cachedPoles.forEach(pole => {
        const isRisk = pole.is_high_risk;
        const color = isRisk ? '#ef4444' : '#10b981';
        
        const marker = L.circleMarker([pole.latitude, pole.longitude], {
            radius: isRisk ? 9 : 7,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85
        });

        marker.bindPopup(`
            <div class="text-xs space-y-1">
                <div class="font-bold text-white flex items-center justify-between">
                    <span>${pole.pole_name}</span>
                    <span class="px-1.5 py-0.5 rounded text-[10px] ${isRisk ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}">
                        ${isRisk ? 'HIGH RISK' : 'NORMAL'}
                    </span>
                </div>
                <div class="text-slate-300">Type: <strong>${pole.pole_type}</strong></div>
                <div class="text-[10px] text-slate-400 font-mono">${pole.latitude.toFixed(6)}, ${pole.longitude.toFixed(6)}</div>
                <div class="pt-1 flex gap-1">
                    <button onclick="quickReportForPole('${pole.pole_name}')" class="w-full px-2 py-1 bg-amber-500 hover:bg-amber-600 rounded text-[10px] font-bold text-slate-950">
                        Report Issue
                    </button>
                </div>
            </div>
        `);
        markersLayer.addLayer(marker);
    });
}

function quickReportForPole(poleName) {
    openReportComplaintModal(poleName);
}

async function loadPoles() {
    try {
        const res = await fetch('/api/poles');
        const json = await res.json();
        if (json.success) {
            cachedPoles = json.data;

            // Populate datalist for official complaint modal
            const datalist = document.getElementById('official-registered-poles-list');
            if (datalist) {
                datalist.innerHTML = cachedPoles.map(p => 
                    `<option value="${p.pole_name}">${p.pole_name} - ${p.pole_type} (${Number(p.latitude).toFixed(6)}, ${Number(p.longitude).toFixed(6)})</option>`
                ).join('');
            }

            const tbody = document.getElementById('poles-table-body');
            tbody.innerHTML = cachedPoles.map(p => `
                <tr class="hover:bg-slate-750">
                    <td class="py-2.5 px-4 font-bold text-slate-400">#${p.pole_id}</td>
                    <td class="py-2.5 px-4 font-semibold text-white">${p.pole_name}</td>
                    <td class="py-2.5 px-4">
                        <span class="px-2 py-0.5 rounded text-[11px] ${
                            p.pole_type === 'Solar' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                            p.pole_type === 'Electrical' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                            'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                        }">${p.pole_type}</span>
                    </td>
                    <td class="py-2.5 px-4 text-slate-400">${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}</td>
                    <td class="py-2.5 px-4">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${p.is_high_risk ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'}">
                            ${p.is_high_risk ? '⚠️ HIGH RISK' : '✓ SECURE'}
                        </span>
                    </td>
                    <td class="py-2.5 px-4 text-right">
                        <button onclick="deletePole(${p.pole_id})" class="text-slate-500 hover:text-red-400 transition" title="Delete Pole">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                </tr>
            `).join('');

            renderMapMarkers();
        }
    } catch (e) {
        console.error('Error loading poles:', e);
    }
}

async function submitPole(e) {
    e.preventDefault();
    const pole_name = document.getElementById('pole-name').value;
    const latitude = document.getElementById('pole-lat').value;
    const longitude = document.getElementById('pole-lon').value;
    const pole_type = document.getElementById('pole-sub-type').value;
    const is_high_risk = document.getElementById('pole-is-risk').checked;

    try {
        const res = await fetch('/api/poles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pole_name, latitude, longitude, pole_type, is_high_risk })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-pole');
            document.getElementById('form-pole').reset();
            loadPoles();
            loadKPIs();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast('Error registering pole', 'error');
    }
}

async function deletePole(id) {
    if (!confirm(`Delete Light Pole #${id}? Sub-entities will be deleted via ON DELETE CASCADE.`)) return;
    try {
        const res = await fetch(`/api/poles/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadPoles();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error deleting pole', 'error');
    }
}

// -------------------------------------------------------------
// Citizens & Complaints
// -------------------------------------------------------------
async function loadCitizens() {
    try {
        const res = await fetch('/api/citizens');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('citizens-table-body');
            tbody.innerHTML = json.data.map(c => `
                <tr class="hover:bg-slate-750">
                    <td class="py-2 px-3 text-slate-400 font-mono">#${c.user_id}</td>
                    <td class="py-2 px-3 font-semibold text-white">${c.first_name} ${c.last_name}</td>
                    <td class="py-2 px-3 text-slate-300 font-mono">${c.email}</td>
                    <td class="py-2 px-3 text-slate-300 font-mono">${c.phone_no}</td>
                    <td class="py-2 px-3 text-slate-400 font-mono">${c.date_of_birth}</td>
                    <td class="py-2 px-3 text-right">
                        <button onclick="deleteCitizen(${c.user_id})" class="text-slate-500 hover:text-red-400 transition">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error('Citizens error:', e);
    }
}

async function submitCitizen(e) {
    e.preventDefault();
    const first_name = document.getElementById('citizen-first-name').value;
    const last_name = document.getElementById('citizen-last-name').value;
    const email = document.getElementById('citizen-email').value;
    const phone_no = document.getElementById('citizen-phone').value;
    const date_of_birth = document.getElementById('citizen-dob').value;

    try {
        const res = await fetch('/api/citizens', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ first_name, last_name, email, phone_no, date_of_birth })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-citizen');
            document.getElementById('form-citizen').reset();
            loadCitizens();
            loadKPIs();
        } else {
            // Emphasize trigger failure if DOB was in the future!
            showToast(`Validation / Trigger Rejection: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast('Error registering citizen', 'error');
    }
}

async function deleteCitizen(id) {
    if (!confirm(`Delete citizen #${id}?`)) return;
    try {
        const res = await fetch(`/api/citizens/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadCitizens();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Failed to delete citizen', 'error');
    }
}

async function loadComplaints() {
    try {
        const res = await fetch('/api/complaints');
        const json = await res.json();
        if (json.success) {
            cachedComplaints = json.data;
            renderComplaintsTable(cachedComplaints);
        }
    } catch (e) {
        console.error('Error loading complaints:', e);
    }
}

function filterComplaints(status) {
    document.querySelectorAll('.complaint-filter').forEach(btn => btn.classList.remove('active-filter'));
    event.currentTarget.classList.add('active-filter');

    if (status === 'ALL') {
        renderComplaintsTable(cachedComplaints);
    } else {
        const filtered = cachedComplaints.filter(c => c.status === status);
        renderComplaintsTable(filtered);
    }
}

function renderComplaintsTable(complaints) {
    const tbody = document.getElementById('complaints-table-body');
    if (!complaints.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-slate-500">No complaints matching filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = complaints.map(c => `
        <tr class="hover:bg-slate-750">
            <td class="py-2.5 px-4 font-mono font-bold text-amber-400">#${c.complaint_id}</td>
            <td class="py-2.5 px-4">
                <div class="font-semibold text-white">${c.issue_type}</div>
                ${c.pole_name ? `<span class="inline-block mt-0.5 px-1.5 py-0.2 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono font-bold">${c.pole_name}</span>` : ''}
            </td>
            <td class="py-2.5 px-4 font-mono">
                ${c.coordinates ? `<span class="text-emerald-400 font-bold">${c.coordinates}</span>` : '<span class="text-slate-500 font-mono italic">Not Tagged</span>'}
            </td>
            <td class="py-2.5 px-4">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold ${
                    c.priority === 'Critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse' :
                    c.priority === 'High' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                    c.priority === 'Medium' ? 'bg-blue-500/20 text-blue-300' : 'bg-slate-700 text-slate-300'
                }">${c.priority}</span>
            </td>
            <td class="py-2.5 px-4">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold ${
                    c.status === 'Resolved' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                    c.status === 'In Progress' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                    'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }">${c.status}</span>
            </td>
            <td class="py-2.5 px-4 text-slate-400 font-mono text-[11px]">${c.created_at || 'Just now'}</td>
            <td class="py-2.5 px-4">
                <span class="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700 text-[10px]">
                    <i class="fa-solid fa-paperclip mr-1"></i> ${c.media_count || 1}
                </span>
            </td>
            <td class="py-2.5 px-4 text-right">
                <div class="flex items-center justify-end gap-1">
                    ${c.status !== 'In Progress' ? `
                        <button onclick="updateComplaintStatus(${c.complaint_id}, 'In Progress')" class="px-2 py-1 bg-blue-600/30 hover:bg-blue-600 border border-blue-500/40 rounded text-[10px] text-blue-300 hover:text-white" title="Move to In Progress">
                            Start
                        </button>
                    ` : ''}
                    ${c.status !== 'Resolved' ? `
                        <button onclick="updateComplaintStatus(${c.complaint_id}, 'Resolved')" class="px-2 py-1 bg-emerald-600/30 hover:bg-emerald-600 border border-emerald-500/40 rounded text-[10px] text-emerald-300 hover:text-white" title="Resolve Ticket">
                            Resolve
                        </button>
                    ` : ''}
                    <button onclick="deleteComplaint(${c.complaint_id})" class="p-1 text-slate-500 hover:text-red-400 ml-1">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

async function submitComplaint(e) {
    e.preventDefault();
    const pole_number = document.getElementById('complaint-pole-number').value.trim().toUpperCase();
    const issue_type = document.getElementById('complaint-issue').value;
    const priority = document.getElementById('complaint-priority').value;
    const status = document.getElementById('complaint-status').value;
    const media_url = document.getElementById('complaint-media-url').value;

    if (!pole_number) {
        showToast('Please enter the pole number stenciled on the pole.', 'error');
        document.getElementById('complaint-pole-number').focus();
        return;
    }

    const matched = cachedPoles.find(p => p.pole_name.toUpperCase() === pole_number);
    if (!matched) {
        showToast(`Pole "${pole_number}" is not registered in the official app. Only registered poles can be reported.`, 'error');
        document.getElementById('complaint-pole-number').focus();
        return;
    }

    try {
        const res = await fetch('/api/complaints', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issue_type, priority, status, media_url, pole_number })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`${data.message} Coordinates [${data.coordinates}] linked automatically.`, 'success');
            closeModal('modal-report-complaint');
            document.getElementById('form-complaint').reset();
            loadComplaints();
            loadMedia();
            loadKPIs();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast('Error filing complaint', 'error');
    }
}

async function updateComplaintStatus(id, newStatus) {
    try {
        const res = await fetch(`/api/complaints/${id}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message + ' (Audit trigger fired)', 'success');
            loadComplaints();
            loadMedia();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error updating status', 'error');
    }
}

async function deleteComplaint(id) {
    if (!confirm(`Delete Complaint #${id}? Attached media in ComplaintMedia will be deleted via ON DELETE CASCADE.`)) return;
    try {
        const res = await fetch(`/api/complaints/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadComplaints();
            loadMedia();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error removing complaint', 'error');
    }
}

// -------------------------------------------------------------
// Complaint Media Gallery
// -------------------------------------------------------------
async function loadMedia() {
    try {
        const res = await fetch('/api/media');
        const json = await res.json();
        if (json.success) {
            const gallery = document.getElementById('media-gallery');
            if (!json.data.length) {
                gallery.innerHTML = `<div class="col-span-full py-8 text-center text-slate-500">No media evidence uploaded yet.</div>`;
                return;
            }

            gallery.innerHTML = json.data.map(m => `
                <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg flex flex-col group">
                    <div class="h-44 w-full bg-slate-900 relative overflow-hidden flex items-center justify-center">
                        <img src="${m.media_url}" alt="Complaint Proof" class="w-full h-full object-cover group-hover:scale-105 transition duration-300" onerror="this.src='https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500&auto=format&fit=crop&q=60'">
                        <span class="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-950/80 text-[10px] font-mono text-amber-300 border border-slate-700">
                            Ticket #${m.complaint_id}
                        </span>
                    </div>
                    <div class="p-3 flex-1 flex flex-col justify-between text-xs space-y-1">
                        <div class="text-[11px] text-slate-400 font-mono truncate" title="${m.media_url}">
                            <i class="fa-solid fa-link mr-1"></i> ${m.media_url}
                        </div>
                        <div class="text-[10px] text-slate-500 font-mono flex items-center justify-between pt-1 border-t border-slate-700/60">
                            <span>${m.uploaded_at || 'Automatic Audit'}</span>
                            <span class="text-emerald-400">Verified</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('Error loading media:', e);
    }
}

async function submitMedia(e) {
    e.preventDefault();
    const complaint_id = document.getElementById('media-complaint-id').value;
    const media_url = document.getElementById('media-url-input').value;

    try {
        const res = await fetch('/api/media', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ complaint_id, media_url })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-media');
            document.getElementById('form-media').reset();
            loadMedia();
            loadComplaints();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast('Error uploading media', 'error');
    }
}

// -------------------------------------------------------------
// Work Orders
// -------------------------------------------------------------
async function loadWorkOrders() {
    try {
        const res = await fetch('/api/workorders');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('workorders-table-body');
            tbody.innerHTML = json.data.map(w => {
                const isCompleted = !!w.completed_date;
                return `
                    <tr class="hover:bg-slate-750">
                        <td class="py-2.5 px-4 font-mono font-bold text-purple-400">#${w.work_order_id}</td>
                        <td class="py-2.5 px-4 font-semibold text-white">${w.vendor_name}</td>
                        <td class="py-2.5 px-4 font-mono text-slate-300">${w.issued_date}</td>
                        <td class="py-2.5 px-4 font-mono text-amber-300 font-bold">₹${parseFloat(w.est_cost).toLocaleString()}</td>
                        <td class="py-2.5 px-4 font-mono text-slate-400">${w.completed_date || '<span class="text-amber-500/80 italic">In Field</span>'}</td>
                        <td class="py-2.5 px-4">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${isCompleted ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'}">
                                ${isCompleted ? '✓ Completed' : '⚡ Active Contract'}
                            </span>
                        </td>
                        <td class="py-2.5 px-4 text-right">
                            <div class="flex items-center justify-end gap-1">
                                ${!isCompleted ? `
                                    <button onclick="completeWorkOrder(${w.work_order_id})" class="px-2 py-1 bg-emerald-600/30 hover:bg-emerald-600 border border-emerald-500/40 rounded text-[10px] text-emerald-300 hover:text-white">
                                        Mark Done
                                    </button>
                                ` : ''}
                                <button onclick="deleteWorkOrder(${w.work_order_id})" class="p-1 text-slate-500 hover:text-red-400 ml-1">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        }
    } catch (e) {
        console.error('Work orders error:', e);
    }
}

async function submitWorkOrder(e) {
    e.preventDefault();
    const vendor_name = document.getElementById('wo-vendor').value;
    const issued_date = document.getElementById('wo-date').value;
    const est_cost = document.getElementById('wo-cost').value;
    const completed_date = document.getElementById('wo-completed').value;

    try {
        const res = await fetch('/api/workorders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vendor_name, issued_date, est_cost, completed_date })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-workorder');
            document.getElementById('form-workorder').reset();
            loadWorkOrders();
            loadKPIs();
        } else {
            showToast(`CHECK Constraint / Error: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast('Error issuing work order', 'error');
    }
}

async function completeWorkOrder(id) {
    try {
        const res = await fetch(`/api/workorders/${id}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadWorkOrders();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error completing work order', 'error');
    }
}

async function deleteWorkOrder(id) {
    if (!confirm(`Delete Work Order #${id}?`)) return;
    try {
        const res = await fetch(`/api/workorders/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadWorkOrders();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error deleting work order', 'error');
    }
}

// -------------------------------------------------------------
// Administration (Divisions, Wards, Officials)
// -------------------------------------------------------------
async function loadDivisions() {
    try {
        const res = await fetch('/api/divisions');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('divisions-table-body');
            tbody.innerHTML = json.data.map(d => `
                <tr class="hover:bg-slate-750">
                    <td class="py-2 px-3 font-mono text-slate-400">#${d.div_id}</td>
                    <td class="py-2 px-3 font-semibold text-white">${d.div_name}</td>
                    <td class="py-2 px-3 text-slate-300">${d.district}</td>
                    <td class="py-2 px-3 text-right">
                        <button onclick="deleteDivision(${d.div_id})" class="text-slate-500 hover:text-red-400">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error('Divisions error:', e);
    }
}

async function submitDivision(e) {
    e.preventDefault();
    const div_name = document.getElementById('div-name').value;
    const district = document.getElementById('div-district').value;
    try {
        const res = await fetch('/api/divisions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ div_name, district })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-division');
            loadDivisions();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Failed to add division', 'error');
    }
}

async function deleteDivision(id) {
    if (!confirm(`Delete Division #${id}?`)) return;
    try {
        const res = await fetch(`/api/divisions/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadDivisions();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error deleting division', 'error');
    }
}

async function loadWards() {
    try {
        const res = await fetch('/api/wards');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('wards-table-body');
            tbody.innerHTML = json.data.map(w => `
                <tr class="hover:bg-slate-750">
                    <td class="py-2 px-3 font-mono text-slate-400">#${w.ward_id}</td>
                    <td class="py-2 px-3 font-semibold text-white">${w.ward_name}</td>
                    <td class="py-2 px-3 text-slate-300">${w.councillor_name}</td>
                    <td class="py-2 px-3 text-right">
                        <button onclick="deleteWard(${w.ward_id})" class="text-slate-500 hover:text-red-400">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error('Wards error:', e);
    }
}

async function submitWard(e) {
    e.preventDefault();
    const ward_name = document.getElementById('ward-name').value;
    const councillor_name = document.getElementById('ward-councillor').value;
    try {
        const res = await fetch('/api/wards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ward_name, councillor_name })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-ward');
            loadWards();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Failed to add ward', 'error');
    }
}

async function deleteWard(id) {
    if (!confirm(`Delete Ward #${id}?`)) return;
    try {
        const res = await fetch(`/api/wards/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadWards();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error deleting ward', 'error');
    }
}

async function loadOfficials() {
    try {
        const res = await fetch('/api/officials');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('officials-table-body');
            tbody.innerHTML = json.data.map(o => `
                <tr class="hover:bg-slate-750">
                    <td class="py-2 px-3 font-mono text-slate-400">#${o.official_id}</td>
                    <td class="py-2 px-3 font-semibold text-white">${o.official_name}</td>
                    <td class="py-2 px-3 text-slate-300">${o.designation}</td>
                    <td class="py-2 px-3 font-mono text-emerald-400">${o.official_email}</td>
                    <td class="py-2 px-3 text-right">
                        <button onclick="deleteOfficial(${o.official_id})" class="text-slate-500 hover:text-red-400">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error('Officials error:', e);
    }
}

async function submitOfficial(e) {
    e.preventDefault();
    const official_name = document.getElementById('official-name').value;
    const designation = document.getElementById('official-desig').value;
    const official_email = document.getElementById('official-email').value;
    try {
        const res = await fetch('/api/officials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ official_name, designation, official_email })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal('modal-add-official');
            loadOfficials();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Failed to register official', 'error');
    }
}

async function deleteOfficial(id) {
    if (!confirm(`Delete Official #${id}?`)) return;
    try {
        const res = await fetch(`/api/officials/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadOfficials();
            loadKPIs();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('Error deleting official', 'error');
    }
}

