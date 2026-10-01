// TOLK Student Cabinet Logic
window.StudentCabinet = {
    data: null,

    async load() {
        if (!State.user || State.user.role !== 'student') {
            showToast("Доступно только для роли Ученик", "warning");
            navigateTo('landing');
            return;
        }

        const container = document.getElementById('student-cabinet-content');
        if (!container) return;

        container.innerHTML = `
            <div class="flex items-center justify-center py-12">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            </div>
        `;

        try {
            const data = await apiFetch('/api/student/dashboard');
            this.data = data;
            this.render();
        } catch (err) {
            container.innerHTML = `
                <div class="tolk-card p-6 text-center text-red-600">
                    <p class="font-bold">Ошибка загрузки личного кабинета</p>
                    <p class="text-sm text-gray-600 mt-1">${err.message}</p>
                </div>
            `;
        }
    },

    render() {
        const container = document.getElementById('student-cabinet-content');
        if (!container || !this.data) return;

        const d = this.data;

        // If student is not enrolled in a group
        if (!d.enrolled || !d.group) {
            this.renderNotEnrolled(container);
            return;
        }

        const g = d.group;
        const strikes = g.strikes || 0;
        const isBlocked = g.is_access_revoked || strikes >= 3;

        // Strike indicator visual rendering
        let strikeIndicatorHtml = '';
        let strikeStatusText = '';

        if (isBlocked) {
            strikeIndicatorHtml = `
                <div class="flex items-center gap-1.5">
                    <div class="strike-dot strike-dot-danger">✕</div>
                    <div class="strike-dot strike-dot-danger">✕</div>
                    <div class="strike-dot strike-dot-danger">✕</div>
                </div>
                <div class="text-xs font-bold text-red-600 bg-red-50 border border-red-200 px-2 py-1 rounded-md">
                    ⛔ 3 / 3 — Доступ аннулирован
                </div>
            `;
            strikeStatusText = `
                <div class="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs sm:text-sm font-medium flex items-start gap-2">
                    <span class="text-base">⚠️</span>
                    <div>
                        <strong>Внимание: доступ к занятиям заблокирован!</strong><br>
                        Вы набрали 3 страйка за невыполненные домашние задания. Обратитесь к администратору (@tolk_admin) для разблокировки.
                    </div>
                </div>
            `;
        } else {
            strikeIndicatorHtml = `
                <div class="flex items-center gap-1.5">
                    <div class="strike-dot ${strikes >= 1 ? 'strike-dot-warning' : 'strike-dot-empty'}">${strikes >= 1 ? '1' : '○'}</div>
                    <div class="strike-dot ${strikes >= 2 ? 'strike-dot-warning' : 'strike-dot-empty'}">${strikes >= 2 ? '2' : '○'}</div>
                    <div class="strike-dot strike-dot-empty">○</div>
                </div>
                <div class="text-xs font-bold ${strikes === 0 ? 'text-emerald-700 bg-emerald-50 border border-emerald-200' : 'text-amber-700 bg-amber-50 border border-amber-200'} px-2.5 py-1 rounded-md">
                    ${strikes === 0 ? '🟢 0 / 3 страйков' : `⚠️ ${strikes} / 3 страйка`}
                </div>
            `;
            strikeStatusText = `
                <p class="text-xs text-gray-500 italic mt-1">
                    «За 3 невыполненных ДЗ доступ к группе аннулируется». Сдавайте задания вовремя, чтобы сохранять место в группе!
                </p>
            `;
        }

        // Google Meet button logic
        let meetButtonHtml = '';
        if (isBlocked) {
            meetButtonHtml = `
                <button disabled class="w-full py-4 px-6 rounded-2xl bg-gray-200 text-gray-500 font-bold text-base cursor-not-allowed flex items-center justify-center gap-3">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>
                    Доступ к уроку заблокирован (3 страйка)
                </button>
            `;
        } else if (g.meet_link) {
            meetButtonHtml = `
                <a href="${g.meet_link}" target="_blank" rel="noopener noreferrer" class="btn-meet w-full py-4 px-6 rounded-2xl font-bold text-base sm:text-lg flex items-center justify-center gap-3 shadow-lg">
                    <span class="text-2xl animate-pulse">🎥</span>
                    <span>Войти на урок в Google Meet</span>
                </a>
            `;
        } else {
            meetButtonHtml = `
                <div class="p-4 bg-orange-50 border border-orange-200 rounded-2xl text-center text-orange-800 text-sm">
                    Тьютор еще не обновил ссылку на Google Meet для этой группы. Ссылка появится перед занятием.
                </div>
            `;
        }

        // Submissions history list
        let submissionsHtml = '';
        if (d.submissions && d.submissions.length > 0) {
            submissionsHtml = d.submissions.map(s => `
                <div class="p-3 bg-gray-50 border border-gray-200 rounded-xl mb-2 flex items-center justify-between">
                    <div class="truncate mr-3">
                        <a href="${s.link}" target="_blank" class="text-sm font-semibold text-orange-600 hover:underline flex items-center gap-1.5 truncate">
                            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                            <span class="truncate">${s.link}</span>
                        </a>
                        ${s.comment ? `<p class="text-xs text-gray-500 mt-0.5">${s.comment}</p>` : ''}
                        <span class="text-[10px] text-gray-400">${s.submitted_at}</span>
                    </div>
                    <div>
                        <span class="text-xs font-semibold px-2 py-1 rounded-full ${
                            s.status === 'approved' ? 'bg-emerald-100 text-emerald-800' :
                            s.status === 'rejected' ? 'bg-red-100 text-red-800' :
                            'bg-blue-100 text-blue-800'
                        }">
                            ${s.status === 'approved' ? 'Принято 👍' : s.status === 'rejected' ? 'Отклонено' : 'Отправлено'}
                        </span>
                    </div>
                </div>
            `).join('');
        } else {
            submissionsHtml = `<p class="text-xs text-gray-400 py-3 text-center">Вы пока не отправили ни одного ДЗ</p>`;
        }

        container.innerHTML = `
            <div class="space-y-6">
                <!-- Group Info Card -->
                <div class="tolk-card p-6">
                    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-4 mb-4">
                        <div>
                            <span class="text-xs font-bold text-orange-600 uppercase tracking-wider">Моя микро-группа</span>
                            <h2 class="text-xl sm:text-2xl font-bold text-gray-900 mt-0.5">${g.group_name}</h2>
                        </div>
                        <span class="badge-orange text-xs font-bold px-3 py-1 rounded-full">
                            ${g.language}
                        </span>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-gray-700 mb-6">
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">📅 Расписание:</span>
                            <strong class="text-gray-900">${g.schedule}</strong>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">🎓 Тьютор:</span>
                            <strong class="text-gray-900">${g.tutor_name || 'Не назначен'}</strong>
                            ${g.tutor_telegram ? `<span class="text-xs text-blue-600">${g.tutor_telegram}</span>` : ''}
                        </div>
                    </div>

                    <!-- Meeting Link Button -->
                    <div class="mb-6">
                        ${meetButtonHtml}
                    </div>

                    <!-- Discipline Tracker (Strict 3-Strike Rule) -->
                    <div class="bg-gray-50 border border-gray-200 rounded-2xl p-4 sm:p-5">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="text-base font-bold text-gray-900">Трекер дисциплины</span>
                                <span class="text-[11px] font-semibold text-gray-500">(Strict 3-Strike Rule)</span>
                            </div>
                            ${strikeIndicatorHtml}
                        </div>
                        ${strikeStatusText}
                    </div>
                </div>

                <!-- Homework Submission Card -->
                <div class="tolk-card p-6">
                    <h3 class="text-lg font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <span>📝 Сдача Домашнего Задания</span>
                    </h3>
                    <p class="text-xs sm:text-sm text-gray-500 mb-4 leading-relaxed">
                        Отправьте ссылку на выполненное задание (Google Drive, видео, аудио или пост). Тьютор проверит его перед следующим уроком.
                    </p>

                    ${isBlocked ? `
                        <div class="p-4 bg-gray-100 text-gray-500 rounded-xl text-center text-sm">
                            Форма сдачи недоступна: доступ к занятиям заблокирован из-за 3 страйков.
                        </div>
                    ` : `
                        <form id="hw-submit-form" onsubmit="StudentCabinet.submitHw(event, ${g.group_id})" class="space-y-3 mb-6">
                            <div>
                                <label class="block text-xs font-semibold text-gray-700 mb-1">Ссылка на ДЗ (Google Drive, видео, аудио)</label>
                                <input type="url" id="hw-link" required placeholder="https://drive.google.com/file/d/..." class="w-full px-3.5 py-2.5 rounded-xl border border-gray-300 focus:border-orange-500 focus:ring-1 focus:ring-orange-500 text-sm">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-gray-700 mb-1">Комментарий (необязательно)</label>
                                <input type="text" id="hw-comment" placeholder="Например: запись монолога на 2 мин" class="w-full px-3.5 py-2 rounded-xl border border-gray-300 focus:border-orange-500 text-sm">
                            </div>
                            <button type="submit" id="btn-submit-hw" class="btn-primary w-full py-2.5 text-sm">
                                🚀 Отправить ДЗ
                            </button>
                        </form>
                    `}

                    <!-- Submissions History -->
                    <div class="border-t border-gray-100 pt-4">
                        <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">История отправленных ДЗ</h4>
                        <div id="hw-submissions-list">
                            ${submissionsHtml}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    renderNotEnrolled(container) {
        const d = this.data;
        const pendingPayment = d.payments && d.payments.find(p => p.status === 'pending');
        const approvedPayment = d.payments && d.payments.find(p => p.status === 'approved');

        container.innerHTML = `
            <div class="space-y-6">
                <div class="tolk-card p-6 sm:p-8 text-center">
                    <div class="w-16 h-16 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
                        ⏳
                    </div>
                    
                    <h2 class="text-xl sm:text-2xl font-bold text-gray-900 mb-2">Добро пожаловать в TOLK!</h2>
                    
                    ${pendingPayment ? `
                        <div class="max-w-md mx-auto p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-sm mb-6 text-left">
                            <div class="font-bold flex items-center gap-1.5 mb-1">
                                <span>🔍 Чек на проверке у Администратора</span>
                            </div>
                            <p class="text-xs text-amber-700">
                                Вы отправили чек за тариф <strong>«${pendingPayment.tariff}»</strong>. Как только администратор проверит чек, вас зачислят в свободную микро-группу (до 5 человек) и здесь появится расписание и ссылка на Google Meet!
                            </p>
                        </div>
                    ` : approvedPayment ? `
                        <div class="max-w-md mx-auto p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm mb-6 text-left">
                            <div class="font-bold flex items-center gap-1.5 mb-1">
                                <span>✅ Оплата подтверждена!</span>
                            </div>
                            <p class="text-xs text-emerald-700">
                                Администратор распределяет вас в группу подходящего уровня. Обычно это занимает от 15 до 60 минут.
                            </p>
                        </div>
                    ` : `
                        <p class="text-gray-600 text-sm max-w-md mx-auto mb-6">
                            Вы еще не зачислены в разговорную микро-группу. Выберите подходящий тариф на главной странице и отправьте чек перевода для старта занятий.
                        </p>
                        <button onclick="navigateTo('landing')" class="btn-primary py-2.5 px-6 text-sm">
                            Выбрать тариф и начать
                        </button>
                    `}
                </div>
            </div>
        `;
    },

    async submitHw(e, groupId) {
        e.preventDefault();
        const link = document.getElementById('hw-link').value.trim();
        const comment = document.getElementById('hw-comment').value.trim();
        const btn = document.getElementById('btn-submit-hw');

        if (!link) {
            showToast("Укажите ссылку на задание", "danger");
            return;
        }

        try {
            if (btn) {
                btn.disabled = true;
                btn.innerText = "Отправка...";
            }

            const res = await apiFetch('/api/student/submit-hw', {
                method: 'POST',
                body: JSON.stringify({
                    group_id: groupId,
                    link: link,
                    comment: comment
                })
            });

            showToast(res.message, "success");
            await this.load();
        } catch (err) {
            showToast(err.message, "danger");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerText = "🚀 Отправить ДЗ";
            }
        }
    }
};
