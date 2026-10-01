// TOLK Tutor Cabinet Logic
window.TutorCabinet = {
    groups: [],
    selectedGroupId: null,
    groupData: null,
    // lesson state for current marking session
    lessonRecords: {}, // { [studentId]: { attended: true, hw_status: 'done', notes: '' } }

    async load() {
        if (!State.user || State.user.role !== 'tutor') {
            showToast("Доступно только для роли Тьютор", "warning");
            navigateTo('landing');
            return;
        }

        const container = document.getElementById('tutor-cabinet-content');
        if (!container) return;

        container.innerHTML = `
            <div class="flex items-center justify-center py-12">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            </div>
        `;

        try {
            const data = await apiFetch('/api/tutor/groups');
            this.groups = data.groups || [];
            
            if (this.groups.length > 0) {
                if (!this.selectedGroupId || !this.groups.find(g => g.id === this.selectedGroupId)) {
                    this.selectedGroupId = this.groups[0].id;
                }
                await this.loadGroupDetails(this.selectedGroupId);
            } else {
                container.innerHTML = `
                    <div class="tolk-card p-8 text-center text-gray-500">
                        <p class="font-bold text-gray-700 text-lg mb-1">У вас пока нет назначенных групп</p>
                        <p class="text-sm">Администратор платформы назначит вам микро-группы студентов.</p>
                    </div>
                `;
            }
        } catch (err) {
            container.innerHTML = `
                <div class="tolk-card p-6 text-center text-red-600">
                    <p class="font-bold">Ошибка загрузки кабинета тьютора</p>
                    <p class="text-sm text-gray-600 mt-1">${err.message}</p>
                </div>
            `;
        }
    },

    async selectGroup(groupId) {
        this.selectedGroupId = groupId;
        await this.loadGroupDetails(groupId);
    },

    async loadGroupDetails(groupId) {
        try {
            const data = await apiFetch(`/api/tutor/groups/${groupId}/students`);
            this.groupData = data;
            
            // Initialize records for all students
            this.lessonRecords = {};
            data.students.forEach(s => {
                this.lessonRecords[s.id] = {
                    student_id: s.id,
                    attended: true,
                    hw_status: 'done',
                    notes: ''
                };
            });

            this.render();
        } catch (err) {
            showToast("Не удалось загрузить данные группы: " + err.message, "danger");
        }
    },

    render() {
        const container = document.getElementById('tutor-cabinet-content');
        if (!container || !this.groupData) return;

        const g = this.groupData.group;
        const students = this.groupData.students || [];

        // Groups tab buttons
        const groupTabsHtml = this.groups.map(groupItem => `
            <button onclick="TutorCabinet.selectGroup(${groupItem.id})" class="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition border ${
                groupItem.id === this.selectedGroupId 
                ? 'bg-orange-500 text-white border-orange-500 shadow-sm' 
                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
            }">
                ${groupItem.name} (${groupItem.enrolled_count}/${groupItem.max_students})
            </button>
        `).join('');

        // Student journal rows
        let studentRowsHtml = '';
        if (students.length === 0) {
            studentRowsHtml = `
                <div class="p-6 text-center text-gray-400 text-sm">
                    В этой группе пока нет учеников
                </div>
            `;
        } else {
            studentRowsHtml = students.map(s => {
                const rec = this.lessonRecords[s.id] || { attended: true, hw_status: 'done' };
                const isBlocked = s.is_blocked || s.strikes >= 3;

                return `
                    <div class="p-4 sm:p-5 border-b border-gray-100 last:border-0 hover:bg-gray-50 transition flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <!-- Student details -->
                        <div class="min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="font-bold text-gray-900 text-sm sm:text-base">${s.full_name}</span>
                                ${s.telegram_username ? `<span class="text-xs text-blue-500 font-medium">${s.telegram_username}</span>` : ''}
                                ${isBlocked ? `<span class="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">⛔ 3 страйка (Блок)</span>` : ''}
                            </div>
                            <div class="text-xs text-gray-500 flex items-center gap-3 mt-1">
                                <span>📱 ${s.phone}</span>
                                <span class="flex items-center gap-1 font-semibold ${
                                    s.strikes === 0 ? 'text-emerald-600' : s.strikes >= 3 ? 'text-red-600' : 'text-amber-600'
                                }">
                                    Страйки: ${s.strikes} / 3
                                </span>
                            </div>

                            <!-- HW submission info if any -->
                            <div class="mt-2 text-xs">
                                ${s.latest_hw_link ? `
                                    <div class="flex items-center gap-1.5 text-orange-600 font-medium bg-orange-50 border border-orange-200 px-2 py-1 rounded-md inline-flex max-w-full truncate">
                                        <span>🔗 Сдано ДЗ:</span>
                                        <a href="${s.latest_hw_link}" target="_blank" class="underline truncate max-w-[200px] sm:max-w-xs">${s.latest_hw_link}</a>
                                        <span class="text-[10px] text-gray-400">(${s.latest_hw_date ? s.latest_hw_date.slice(0, 10) : ''})</span>
                                    </div>
                                ` : `
                                    <span class="text-gray-400 italic">ДЗ не загружено</span>
                                `}
                            </div>
                        </div>

                        <!-- Interactive Journal Controls -->
                        <div class="flex flex-wrap items-center gap-2">
                            <!-- Attendance Buttons -->
                            <div class="flex rounded-lg p-1 bg-gray-100 border border-gray-200">
                                <button type="button" onclick="TutorCabinet.setAttendance(${s.id}, true)" class="px-2.5 py-1 text-xs font-bold rounded-md transition ${
                                    rec.attended ? 'bg-emerald-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                                }">
                                    Check-in ✅
                                </button>
                                <button type="button" onclick="TutorCabinet.setAttendance(${s.id}, false)" class="px-2.5 py-1 text-xs font-bold rounded-md transition ${
                                    !rec.attended ? 'bg-red-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                                }">
                                    Пропуск ❌
                                </button>
                            </div>

                            <!-- HW Buttons -->
                            <div class="flex rounded-lg p-1 bg-gray-100 border border-gray-200">
                                <button type="button" onclick="TutorCabinet.setHwStatus(${s.id}, 'done')" class="px-2.5 py-1 text-xs font-bold rounded-md transition ${
                                    rec.hw_status === 'done' ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                                }">
                                    ДЗ сдано 👍
                                </button>
                                <button type="button" onclick="TutorCabinet.setHwStatus(${s.id}, 'strike')" class="px-2.5 py-1 text-xs font-bold rounded-md transition ${
                                    rec.hw_status === 'strike' ? 'bg-red-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                                }">
                                    ❌ Поставить Страйк
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        container.innerHTML = `
            <div class="space-y-6">
                <!-- Group Switcher Bar -->
                <div>
                    <div class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Мои активные микро-группы (до 5 человек)</div>
                    <div class="flex flex-wrap gap-2">
                        ${groupTabsHtml}
                    </div>
                </div>

                <!-- Google Meet Link Setting Card -->
                <div class="tolk-card p-6">
                    <h3 class="text-base font-bold text-gray-900 mb-1 flex items-center gap-2">
                        <span>⚙️ Настройка постоянной ссылки Google Meet</span>
                    </h3>
                    <p class="text-xs text-gray-500 mb-3">
                        Ученики этой группы видят эту ссылку в своем личном кабинете на большой кнопке перехода на урок.
                    </p>

                    <form onsubmit="TutorCabinet.saveMeetLink(event)" class="flex flex-col sm:flex-row gap-2">
                        <input type="url" id="tutor-meet-link" value="${g.meet_link || ''}" placeholder="https://meet.google.com/xxx-yyyy-zzz" required class="flex-1 px-3.5 py-2 rounded-xl border border-gray-300 focus:border-orange-500 text-sm">
                        <button type="submit" id="btn-save-meet" class="btn-primary py-2 px-5 text-sm shrink-0">
                            💾 Сохранить ссылку
                        </button>
                    </form>
                </div>

                <!-- Electronic Journal Card -->
                <div class="tolk-card overflow-hidden">
                    <div class="p-5 bg-gray-50 border-b border-gray-200 flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h3 class="text-base sm:text-lg font-bold text-gray-900">📖 Электронный журнал группы</h3>
                            <p class="text-xs text-gray-500">${g.name} • Расписание: ${g.schedule}</p>
                        </div>
                        <div class="flex items-center gap-2">
                            <input type="text" id="lesson-topic" placeholder="Тема урока (например: Unit 4. Work & Study)" class="px-3 py-1.5 border border-gray-300 rounded-lg text-xs w-48 sm:w-64 focus:border-orange-500">
                        </div>
                    </div>

                    <div class="divide-y divide-gray-100">
                        ${studentRowsHtml}
                    </div>

                    <div class="p-5 bg-gray-50 border-t border-gray-200 flex items-center justify-between flex-wrap gap-3">
                        <div class="text-xs text-gray-500">
                            💡 Кнопка <strong>«Поставить Страйк»</strong> автоматически добавит 1 страйк в личный кабинет ученика при сохранении.
                        </div>
                        <button onclick="TutorCabinet.saveLessonResults()" id="btn-save-lesson" class="btn-primary py-2.5 px-6 text-sm shadow-md">
                            💾 Сохранить результаты урока
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    setAttendance(studentId, attended) {
        if (!this.lessonRecords[studentId]) return;
        this.lessonRecords[studentId].attended = attended;
        this.render();
    },

    setHwStatus(studentId, hwStatus) {
        if (!this.lessonRecords[studentId]) return;
        this.lessonRecords[studentId].hw_status = hwStatus;
        this.render();
    },

    async saveMeetLink(e) {
        e.preventDefault();
        const link = document.getElementById('tutor-meet-link').value.trim();
        const btn = document.getElementById('btn-save-meet');

        try {
            if (btn) {
                btn.disabled = true;
                btn.innerText = "Сохранение...";
            }

            const res = await apiFetch('/api/tutor/update-meet-link', {
                method: 'POST',
                body: JSON.stringify({
                    group_id: this.selectedGroupId,
                    meet_link: link
                })
            });

            showToast(res.message, "success");
            if (this.groupData && this.groupData.group) {
                this.groupData.group.meet_link = link;
            }
        } catch (err) {
            showToast(err.message, "danger");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerText = "💾 Сохранить ссылку";
            }
        }
    },

    async saveLessonResults() {
        const btn = document.getElementById('btn-save-lesson');
        const topic = document.getElementById('lesson-topic') ? document.getElementById('lesson-topic').value : '';

        const records = Object.values(this.lessonRecords);

        try {
            if (btn) {
                btn.disabled = true;
                btn.innerText = "Сохранение...";
            }

            const res = await apiFetch('/api/tutor/save-lesson', {
                method: 'POST',
                body: JSON.stringify({
                    group_id: this.selectedGroupId,
                    topic: topic,
                    records: records
                })
            });

            showToast(res.message, "success");
            // Reload group details to refresh strikes
            await this.loadGroupDetails(this.selectedGroupId);
        } catch (err) {
            showToast(err.message, "danger");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerText = "💾 Сохранить результаты урока";
            }
        }
    }
};
