// TOLK Admin Panel Logic
window.AdminPanel = {
    overview: null,
    activeTab: 'payments', // 'payments', 'groups', 'violations'

    async load() {
        if (!State.user || State.user.role !== 'admin') {
            showToast("Доступно только для Администратора", "warning");
            navigateTo('landing');
            return;
        }

        const container = document.getElementById('admin-cabinet-content');
        if (!container) return;

        container.innerHTML = `
            <div class="flex items-center justify-center py-12">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            </div>
        `;

        try {
            const data = await apiFetch('/api/admin/overview');
            this.overview = data;
            this.render();
        } catch (err) {
            container.innerHTML = `
                <div class="tolk-card p-6 text-center text-red-600">
                    <p class="font-bold">Ошибка загрузки панели администратора</p>
                    <p class="text-sm text-gray-600 mt-1">${err.message}</p>
                </div>
            `;
        }
    },

    setTab(tab) {
        this.activeTab = tab;
        this.render();
    },

    render() {
        const container = document.getElementById('admin-cabinet-content');
        if (!container || !this.overview) return;

        const ov = this.overview;
        const stats = ov.stats;

        container.innerHTML = `
            <div class="space-y-6">
                <!-- Admin Header & Stats -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                    <div class="tolk-card p-4">
                        <span class="text-xs text-gray-500 font-medium">Микро-группы</span>
                        <div class="text-xl sm:text-2xl font-bold text-gray-900 mt-1">${stats.total_groups}</div>
                    </div>
                    <div class="tolk-card p-4">
                        <span class="text-xs text-gray-500 font-medium">Всего учеников</span>
                        <div class="text-xl sm:text-2xl font-bold text-gray-900 mt-1">${stats.total_students}</div>
                    </div>
                    <div class="tolk-card p-4">
                        <span class="text-xs text-gray-500 font-medium">Чеки на проверке</span>
                        <div class="text-xl sm:text-2xl font-bold text-amber-600 mt-1">${stats.pending_payments}</div>
                    </div>
                    <div class="tolk-card p-4">
                        <span class="text-xs text-gray-500 font-medium">3-Strike Нарушения</span>
                        <div class="text-xl sm:text-2xl font-bold text-red-600 mt-1">${stats.striked_students}</div>
                    </div>
                </div>

                <!-- Admin Tabs Navigation -->
                <div class="flex flex-wrap gap-2 border-b border-gray-200 pb-3">
                    <button onclick="AdminPanel.setTab('payments')" class="px-4 py-2 rounded-xl text-sm font-bold transition flex items-center gap-2 ${
                        this.activeTab === 'payments' ? 'bg-orange-500 text-white shadow-sm' : 'bg-white text-gray-600 hover:bg-gray-100'
                    }">
                        <span>💳 Подтверждение Оплат</span>
                        ${stats.pending_payments > 0 ? `<span class="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">${stats.pending_payments}</span>` : ''}
                    </button>
                    <button onclick="AdminPanel.setTab('groups')" class="px-4 py-2 rounded-xl text-sm font-bold transition flex items-center gap-2 ${
                        this.activeTab === 'groups' ? 'bg-orange-500 text-white shadow-sm' : 'bg-white text-gray-600 hover:bg-gray-100'
                    }">
                        <span>👥 Управление микро-группами</span>
                    </button>
                    <button onclick="AdminPanel.setTab('violations')" class="px-4 py-2 rounded-xl text-sm font-bold transition flex items-center gap-2 ${
                        this.activeTab === 'violations' ? 'bg-orange-500 text-white shadow-sm' : 'bg-white text-gray-600 hover:bg-gray-100'
                    }">
                        <span>⚠️ Лог нарушений (3-Strike)</span>
                        ${stats.striked_students > 0 ? `<span class="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">${stats.striked_students}</span>` : ''}
                    </button>
                </div>

                <!-- Tab Content -->
                <div id="admin-tab-content">
                    ${this.renderActiveTabContent()}
                </div>
            </div>
        `;
    },

    renderActiveTabContent() {
        if (this.activeTab === 'payments') {
            return this.renderPaymentsTab();
        } else if (this.activeTab === 'groups') {
            return this.renderGroupsTab();
        } else {
            return this.renderViolationsTab();
        }
    },

    // 1. Manual Payments Tab
    renderPaymentsTab() {
        const payments = this.overview.payments || [];
        if (payments.length === 0) {
            return `<div class="tolk-card p-8 text-center text-gray-400">Нет заявок на оплату</div>`;
        }

        return `
            <div class="tolk-card overflow-hidden">
                <div class="p-4 sm:p-5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                    <h3 class="font-bold text-gray-900 text-base">Заявки на оплату (Ручная сверка чеков)</h3>
                    <span class="text-xs text-gray-500">Без автоматических шлюзов: Click / Payme чеки</span>
                </div>
                <div class="divide-y divide-gray-100">
                    ${payments.map(p => `
                        <div class="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50 transition">
                            <div class="flex items-start gap-4">
                                <!-- Receipt Thumbnail with Zoom Modal -->
                                <div onclick="AdminPanel.previewReceipt('/uploads/receipts/${p.receipt_filename}')" class="cursor-pointer group relative shrink-0">
                                    <img src="/uploads/receipts/${p.receipt_filename}" alt="Receipt" class="w-16 h-20 object-cover rounded-lg border border-gray-200 group-hover:opacity-80 transition shadow-sm">
                                    <div class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-30 rounded-lg opacity-0 group-hover:opacity-100 transition">
                                        <span class="text-white text-xs font-bold">🔍</span>
                                    </div>
                                </div>

                                <div>
                                    <div class="flex items-center gap-2">
                                        <h4 class="font-bold text-gray-900 text-base">${p.student_name}</h4>
                                        <span class="text-xs text-gray-500">${p.student_phone}</span>
                                        ${p.telegram_username ? `<span class="text-xs text-blue-500">${p.telegram_username}</span>` : ''}
                                    </div>
                                    <div class="text-sm font-semibold text-orange-600 mt-0.5">
                                        ${p.tariff} — ${Number(p.amount).toLocaleString()} UZS
                                    </div>
                                    <div class="text-xs text-gray-400 mt-1">
                                        Дата заявки: ${p.created_at}
                                    </div>
                                    <div class="mt-1">
                                        <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${
                                            p.status === 'approved' ? 'bg-emerald-100 text-emerald-800' :
                                            p.status === 'rejected' ? 'bg-red-100 text-red-800' :
                                            'bg-amber-100 text-amber-800'
                                        }">
                                            ${p.status === 'approved' ? '✅ Одобрена' : p.status === 'rejected' ? '❌ Отклонена' : '⏳ Ожидает проверки'}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <!-- Action Buttons -->
                            <div class="flex items-center gap-2 self-end md:self-center">
                                ${p.status === 'pending' ? `
                                    <button onclick="AdminPanel.reviewPayment(${p.id}, 'approved')" class="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1 shadow-sm transition">
                                        <span>✅ Подтвердить оплату</span>
                                    </button>
                                    <button onclick="AdminPanel.reviewPayment(${p.id}, 'rejected')" class="px-3.5 py-2 bg-gray-100 hover:bg-red-50 text-red-600 hover:border-red-200 border border-gray-200 rounded-xl text-xs font-bold transition">
                                        <span>❌ Отклонить</span>
                                    </button>
                                ` : `
                                    <span class="text-xs text-gray-400 italic">Обработано</span>
                                `}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    },

    // 2. Micro-Groups Management Tab
    renderGroupsTab() {
        const groups = this.overview.groups || [];
        const unassigned = this.overview.unassigned_students || [];

        return `
            <div class="space-y-6">
                <!-- Group Actions Bar -->
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <p class="text-xs text-gray-500 font-medium">
                        В каждой микро-группе действует жесткое ограничение: <strong>максимум 5 учеников</strong> для гарантии разговорной практики.
                    </p>
                    <button onclick="openModal('createGroupModal')" class="btn-primary py-2 px-4 text-xs sm:text-sm">
                        + Создать новую микро-группу
                    </button>
                </div>

                <!-- Unassigned Students (Ready to be enrolled) -->
                ${unassigned.length > 0 ? `
                    <div class="p-4 bg-orange-50 border border-orange-200 rounded-2xl">
                        <h4 class="font-bold text-orange-900 text-sm mb-2 flex items-center gap-1.5">
                            <span>🎓 Студенты, готовые к зачислению (${unassigned.length}):</span>
                        </h4>
                        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                            ${unassigned.map(s => `
                                <div class="bg-white p-2.5 rounded-xl border border-orange-100 text-xs flex items-center justify-between">
                                    <div>
                                        <div class="font-bold text-gray-800">${s.full_name}</div>
                                        <div class="text-gray-500">${s.phone} ${s.paid_tariff ? `• ${s.paid_tariff}` : ''}</div>
                                    </div>
                                    <button onclick="AdminPanel.openAssignModal(${s.id}, '${s.full_name}')" class="text-orange-600 font-bold hover:underline ml-2">
                                        Зачислить →
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <!-- Groups List -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    ${groups.map(g => {
                        const isFull = g.enrolled_count >= g.max_students;
                        return `
                            <div class="tolk-card p-5 flex flex-col justify-between">
                                <div>
                                    <div class="flex items-start justify-between gap-2 mb-2">
                                        <div>
                                            <span class="text-[11px] font-bold text-orange-600 uppercase tracking-wider">${g.language}</span>
                                            <h4 class="text-base font-bold text-gray-900">${g.name}</h4>
                                        </div>
                                        <span class="text-xs font-bold px-2 py-1 rounded-full ${
                                            isFull ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
                                        }">
                                            ${g.enrolled_count} / ${g.max_students} чел. ${isFull ? '(Заполнена)' : ''}
                                        </span>
                                    </div>

                                    <div class="text-xs text-gray-600 space-y-1 mb-4 bg-gray-50 p-2.5 rounded-xl border border-gray-100">
                                        <div><strong>Расписание:</strong> ${g.schedule}</div>
                                        <div><strong>Тьютор:</strong> ${g.tutor_name || 'Не назначен'} (${g.tutor_phone || ''})</div>
                                        <div class="truncate"><strong>Meet:</strong> <a href="${g.meet_link}" target="_blank" class="text-orange-600 underline">${g.meet_link || 'Не указана'}</a></div>
                                    </div>

                                    <!-- Enrolled Students List -->
                                    <div class="mb-4">
                                        <div class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5">Состав группы:</div>
                                        ${g.students && g.students.length > 0 ? `
                                            <div class="space-y-1.5">
                                                ${g.students.map(s => `
                                                    <div class="flex items-center justify-between text-xs p-1.5 bg-white border border-gray-100 rounded-lg">
                                                        <div class="flex items-center gap-1.5">
                                                            <span class="font-medium text-gray-900">${s.full_name}</span>
                                                            <span class="text-[10px] ${s.strikes >= 3 ? 'text-red-600 font-bold' : 'text-gray-400'}">(${s.strikes} страйка)</span>
                                                        </div>
                                                        <button onclick="AdminPanel.removeStudentFromGroup(${g.id}, ${s.id})" title="Исключить из группы" class="text-gray-400 hover:text-red-500 p-0.5">
                                                            ✕
                                                        </button>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        ` : `
                                            <p class="text-xs text-gray-400 italic">В группе пока нет учеников</p>
                                        `}
                                    </div>
                                </div>

                                <div class="pt-3 border-t border-gray-100 flex items-center justify-between">
                                    <span class="text-xs text-gray-400">Свободно мест: ${g.max_students - g.enrolled_count}</span>
                                    ${!isFull && unassigned.length > 0 ? `
                                        <button onclick="AdminPanel.openAssignToGroupModal(${g.id}, '${g.name}')" class="text-xs font-bold text-orange-600 hover:text-orange-700">
                                            + Добавить ученика
                                        </button>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    },

    // 3. Violations Log Tab (Strict 3-Strike Rule)
    renderViolationsTab() {
        const violations = this.overview.violations || [];

        return `
            <div class="tolk-card overflow-hidden">
                <div class="p-5 bg-red-50 border-b border-red-200 flex flex-wrap items-center justify-between gap-2">
                    <div>
                        <h3 class="font-bold text-red-900 text-base flex items-center gap-2">
                            <span>⛔ Лог нарушений дисциплины (Strict 3-Strike Rule)</span>
                        </h3>
                        <p class="text-xs text-red-700 mt-0.5">
                            Ученики, получившие 3 страйка за систематически несданные домашние задания.
                        </p>
                    </div>
                </div>

                ${violations.length === 0 ? `
                    <div class="p-8 text-center text-gray-400 text-sm">
                        Нарушителей нет. Все ученики соблюдают регламент выполнения ДЗ! 👏
                    </div>
                ` : `
                    <div class="divide-y divide-gray-100">
                        ${violations.map(v => `
                            <div class="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50 transition">
                                <div>
                                    <div class="flex items-center gap-2">
                                        <h4 class="font-bold text-gray-900 text-base">${v.student_name}</h4>
                                        <span class="bg-red-500 text-white text-[11px] font-bold px-2 py-0.5 rounded-full">
                                            🔴 ${v.strikes} / 3 страйка
                                        </span>
                                        ${v.is_blocked ? `<span class="bg-gray-800 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">Заблокирован</span>` : ''}
                                    </div>
                                    <div class="text-xs text-gray-500 mt-1 flex flex-wrap gap-x-3 gap-y-1">
                                        <span>📱 ${v.phone}</span>
                                        <span>Группа: <strong>${v.group_name}</strong></span>
                                        <span>Тьютор: <strong>${v.tutor_name || 'Не указан'}</strong></span>
                                    </div>
                                </div>

                                <div class="flex items-center gap-2 self-end md:self-center">
                                    ${!v.is_blocked ? `
                                        <button onclick="AdminPanel.blockStudent(${v.student_id}, ${v.group_id})" class="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold shadow-sm transition">
                                            ⛔ Исключить / Заблокировать
                                        </button>
                                    ` : `
                                        <button onclick="AdminPanel.unblockStudent(${v.student_id}, ${v.group_id})" class="px-3 py-1.5 bg-gray-700 hover:bg-gray-800 text-white rounded-xl text-xs font-bold transition">
                                            🔓 Разблокировать
                                        </button>
                                    `}
                                    <button onclick="AdminPanel.resetStrikes(${v.student_id}, ${v.group_id})" class="px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-xl text-xs font-semibold transition">
                                        Сбросить страйки
                                    </button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `}
            </div>
        `;
    },

    previewReceipt(url) {
        const modalImg = document.getElementById('receipt-preview-img');
        if (modalImg) modalImg.src = url;
        openModal('receiptModal');
    },

    async reviewPayment(paymentId, status) {
        try {
            const res = await apiFetch(`/api/admin/review-payment/${paymentId}`, {
                method: 'POST',
                body: JSON.stringify({
                    status: status,
                    admin_comment: status === 'approved' ? 'Подтверждено администратором' : 'Отклонено'
                })
            });
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    },

    openAssignModal(studentId, studentName) {
        const select = document.getElementById('assign-group-select');
        const hiddenStudent = document.getElementById('assign-student-id');
        const label = document.getElementById('assign-student-name-label');

        if (!select || !this.overview) return;

        hiddenStudent.value = studentId;
        label.innerText = studentName;

        // Populate available groups (that have space < 5)
        const availableGroups = this.overview.groups.filter(g => g.enrolled_count < g.max_students);
        if (availableGroups.length === 0) {
            showToast("Нет свободных мест ни в одной группе. Создайте новую группу.", "warning");
            return;
        }

        select.innerHTML = availableGroups.map(g => `
            <option value="${g.id}">${g.name} (${g.enrolled_count}/${g.max_students} чел.) — ${g.schedule}</option>
        `).join('');

        openModal('assignStudentModal');
    },

    openAssignToGroupModal(groupId, groupName) {
        const unassigned = this.overview.unassigned_students || [];
        if (unassigned.length === 0) {
            showToast("Нет свободных студентов для зачисления", "info");
            return;
        }
        this.openAssignModal(unassigned[0].id, unassigned[0].full_name);
    },

    async submitAssignStudent(e) {
        e.preventDefault();
        const studentId = parseInt(document.getElementById('assign-student-id').value);
        const groupId = parseInt(document.getElementById('assign-group-select').value);

        try {
            const res = await apiFetch('/api/admin/groups/assign-student', {
                method: 'POST',
                body: JSON.stringify({
                    group_id: groupId,
                    student_id: studentId
                })
            });
            closeModal('assignStudentModal');
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    },

    async removeStudentFromGroup(groupId, studentId) {
        if (!confirm("Вы уверены, что хотите удалить ученика из этой группы?")) return;
        try {
            const res = await apiFetch('/api/admin/groups/remove-student', {
                method: 'POST',
                body: JSON.stringify({
                    group_id: groupId,
                    student_id: studentId
                })
            });
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    },

    async blockStudent(studentId, groupId) {
        if (!confirm("Исключить ученика из группы и заблокировать доступ к занятиям?")) return;
        try {
            const res = await apiFetch('/api/admin/block-student', {
                method: 'POST',
                body: JSON.stringify({
                    student_id: studentId,
                    group_id: groupId,
                    is_blocked: true
                })
            });
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    },

    async unblockStudent(studentId, groupId) {
        try {
            const res = await apiFetch('/api/admin/block-student', {
                method: 'POST',
                body: JSON.stringify({
                    student_id: studentId,
                    group_id: groupId,
                    is_blocked: false
                })
            });
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    },

    async resetStrikes(studentId, groupId) {
        if (!confirm("Сбросить все страйки для этого ученика?")) return;
        try {
            const res = await apiFetch('/api/admin/reset-strikes', {
                method: 'POST',
                body: JSON.stringify({
                    student_id: studentId,
                    group_id: groupId,
                    action: 'reset'
                })
            });
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    },

    async createGroup(e) {
        e.preventDefault();
        const form = document.getElementById('create-group-form');
        const name = document.getElementById('new-group-name').value.trim();
        const language = document.getElementById('new-group-lang').value.trim();
        const tariff = document.getElementById('new-group-tariff').value.trim();
        const schedule = document.getElementById('new-group-schedule').value.trim();
        const tutorId = parseInt(document.getElementById('new-group-tutor').value);
        const meetLink = document.getElementById('new-group-meet').value.trim();

        try {
            const res = await apiFetch('/api/admin/groups/create', {
                method: 'POST',
                body: JSON.stringify({
                    name, language, tariff, schedule, tutor_id: tutorId, meet_link: meetLink
                })
            });
            closeModal('createGroupModal');
            form.reset();
            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        }
    }
};
