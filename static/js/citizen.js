// LumiSafe - Citizen Portal Client Logic

let citizenMapInstance = null;
let citizenMarkersLayer = null;
let cachedCitizenPoles = [];
let cachedAllComplaints = [];
let cachedMyComplaints = [];

document.addEventListener('DOMContentLoaded', () => {
    initCitizenApp();
});

async function initCitizenApp() {
    await loadCitizenPoles();
    await loadAllCitizenComplaints();
    await loadMyCitizenComplaints();
    initCitizenMap();
}

function switchCitizenTab(tabName) {
    document.querySelectorAll('.citizen-tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active-tab'));

    const targetTab = document.getElementById(`citizen-tab-${tabName}`);
    if (targetTab) {
        targetTab.classList.remove('hidden');
    }

    event.currentTarget?.classList.add('active-tab');

    if (tabName === 'map') {
        setTimeout(() => {
            if (citizenMapInstance) citizenMapInstance.invalidateSize();
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
        const poleInput = document.getElementById('citizen-pole-number');
        if (poleInput) poleInput.value = poleName;
        document.getElementById('citizen-issue-type').value = 'Bulb Failure';
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const colors = {
        success: 'bg-emerald-600 text-white border-emerald-400',
        error: 'bg-red-600 text-white border-red-400',
        info: 'bg-blue-600 text-white border-blue-400'
    };
    toast.className = `px-4 py-3 rounded-lg shadow-2xl border text-xs flex items-center gap-2 pointer-events-auto ${colors[type] || colors.info}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4000);
}

// -------------------------------------------------------------
// GIS Map & Poles
// -------------------------------------------------------------
function initCitizenMap() {
    if (citizenMapInstance) return;
    const defaultCenter = [12.935, 77.64];
    citizenMapInstance = L.map('citizen-map').setView(defaultCenter, 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(citizenMapInstance);

    citizenMarkersLayer = L.layerGroup().addTo(citizenMapInstance);
    renderCitizenMapMarkers();
}

function renderCitizenMapMarkers() {
    if (!citizenMarkersLayer) return;
    citizenMarkersLayer.clearLayers();

    cachedCitizenPoles.forEach(pole => {
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
                <div class="pt-2">
                    <button onclick="openReportComplaintModal('${pole.pole_name}')" class="w-full px-2 py-1 bg-amber-500 hover:bg-amber-600 rounded text-[10px] font-bold text-slate-950">
                        Report Issue on This Pole
                    </button>
                </div>
            </div>
        `);
        citizenMarkersLayer.addLayer(marker);
    });
}

async function loadCitizenPoles() {
    try {
        const res = await fetch('/api/poles');
        const json = await res.json();
        if (json.success) {
            cachedCitizenPoles = json.data;
            document.getElementById('total-poles-counter').textContent = cachedCitizenPoles.length;

            // Populate datalist for complaint modal
            const datalist = document.getElementById('citizen-registered-poles-list');
            if (datalist) {
                datalist.innerHTML = cachedCitizenPoles.map(p => 
                    `<option value="${p.pole_name}">${p.pole_name} - ${p.pole_type} (${Number(p.latitude).toFixed(6)}, ${Number(p.longitude).toFixed(6)})</option>`
                ).join('');
            }

            const list = document.getElementById('citizen-poles-list');
            list.innerHTML = cachedCitizenPoles.map(p => `
                <div class="p-2 rounded bg-slate-900 border border-slate-700/60 flex items-center justify-between hover:bg-slate-750 transition cursor-pointer" onclick="openReportComplaintModal('${p.pole_name}')">
                    <div>
                        <div class="font-bold text-white">${p.pole_name}</div>
                        <div class="text-[10px] text-slate-400 font-mono">${p.pole_type} &bull; ${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}</div>
                    </div>
                    <span class="px-2 py-0.5 rounded text-[10px] ${p.is_high_risk ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'} font-semibold">
                        ${p.is_high_risk ? 'High Risk' : 'Secure'}
                    </span>
                </div>
            `).join('');

            renderCitizenMapMarkers();
        }
    } catch (e) {
        console.error('Error loading citizen poles:', e);
    }
}

// -------------------------------------------------------------
// Complaints Management (All Complaints + My Filed Complaints)
// -------------------------------------------------------------
async function loadAllCitizenComplaints() {
    try {
        const res = await fetch('/api/complaints');
        const json = await res.json();
        if (json.success) {
            cachedAllComplaints = json.data;
            renderAllComplaintsTable(cachedAllComplaints);
        }
    } catch (e) {
        console.error('Error loading complaints:', e);
    }
}

function filterCitizenComplaints(status) {
    document.querySelectorAll('.citizen-complaint-filter').forEach(btn => btn.classList.remove('active-filter'));
    event.currentTarget.classList.add('active-filter');

    if (status === 'ALL') {
        renderAllComplaintsTable(cachedAllComplaints);
    } else {
        const filtered = cachedAllComplaints.filter(c => c.status === status);
        renderAllComplaintsTable(filtered);
    }
}

function renderAllComplaintsTable(complaints) {
    const tbody = document.getElementById('citizen-all-complaints-body');
    if (!complaints.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-500">No complaints matching filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = complaints.map(c => `
        <tr class="hover:bg-slate-750">
            <td class="py-2.5 px-4 font-bold text-amber-400">#${c.complaint_id}</td>
            <td class="py-2.5 px-4">
                <div class="font-semibold text-white">${c.issue_type}</div>
                ${c.pole_name ? `<span class="inline-block mt-0.5 px-1.5 py-0.2 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono font-bold">${c.pole_name}</span>` : ''}
            </td>
            <td class="py-2.5 px-4 font-mono">
                ${c.coordinates ? `<span class="text-emerald-400 font-bold">${c.coordinates}</span>` : '<span class="text-slate-500 font-mono italic">Not Tagged</span>'}
            </td>
            <td class="py-2.5 px-4">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold ${
                    c.priority === 'Critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
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
            <td class="py-2.5 px-4 text-slate-400 text-[11px]">${c.created_at || 'Recently'}</td>
            <td class="py-2.5 px-4 text-right">
                <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300 text-[10px]">
                    <i class="fa-solid fa-camera mr-1"></i> ${c.media_count || 1} Proofs
                </span>
            </td>
        </tr>
    `).join('');
}

async function loadMyCitizenComplaints() {
    try {
        const res = await fetch('/api/citizen/my-complaints');
        const json = await res.json();
        if (json.success) {
            cachedMyComplaints = json.data;
            document.getElementById('my-tickets-count').textContent = cachedMyComplaints.length;

            const tbody = document.getElementById('citizen-my-complaints-body');
            if (!cachedMyComplaints.length) {
                tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-500">You haven't filed any complaints in this session yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = cachedMyComplaints.map(c => `
                <tr class="hover:bg-slate-750">
                    <td class="py-2.5 px-4 font-bold text-emerald-400">#${c.complaint_id}</td>
                    <td class="py-2.5 px-4">
                        <div class="font-semibold text-white">${c.issue_type}</div>
                        ${c.pole_name ? `<span class="inline-block mt-0.5 px-1.5 py-0.2 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono font-bold">${c.pole_name}</span>` : ''}
                    </td>
                    <td class="py-2.5 px-4 font-mono">
                        ${c.coordinates ? `<span class="text-emerald-400 font-bold">${c.coordinates}</span>` : '<span class="text-slate-500 font-mono italic">Not Tagged</span>'}
                    </td>
                    <td class="py-2.5 px-4">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold ${
                            c.priority === 'Critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
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
                    <td class="py-2.5 px-4 text-slate-400 text-[11px]">${c.created_at || 'Recently'}</td>
                    <td class="py-2.5 px-4 text-right">
                        <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-emerald-400 text-[10px]">
                            <i class="fa-solid fa-check-circle mr-1"></i> Logged
                        </span>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error('Error loading my complaints:', e);
    }
}

async function submitCitizenComplaint(e) {
    e.preventDefault();
    const pole_number = document.getElementById('citizen-pole-number').value.trim().toUpperCase();
    const issue_type = document.getElementById('citizen-issue-type').value;
    const priority = document.getElementById('citizen-priority').value;
    const media_url = document.getElementById('citizen-media-url').value.trim();

    if (!pole_number) {
        showToast('Please enter the pole number stenciled on the pole.', 'error');
        document.getElementById('citizen-pole-number').focus();
        return;
    }

    // Verify pole is registered in official app
    const registeredMatch = cachedCitizenPoles.find(p => p.pole_name.toUpperCase() === pole_number);
    if (!registeredMatch) {
        showToast(`Pole "${pole_number}" is not registered in the official app. Only registered poles can be reported.`, 'error');
        document.getElementById('citizen-pole-number').focus();
        return;
    }

    try {
        const res = await fetch('/api/complaints', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issue_type, priority, status: 'Open', media_url, pole_number })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`${data.message} Coordinates [${data.coordinates}] linked automatically.`, 'success');
            closeModal('modal-report-complaint');
            document.getElementById('citizen-form-complaint').reset();
            loadAllCitizenComplaints();
            loadMyCitizenComplaints();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (err) {
        showToast('Error filing complaint', 'error');
    }
}

