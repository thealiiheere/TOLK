// TOLK Landing Page Logic
window.Landing = {
    tariffs: [],

    async init() {
        await this.loadTariffs();
        this.setupEventListeners();
    },

    async loadTariffs() {
        const container = document.getElementById('tariffs-grid');
        if (!container) return;

        try {
            const res = await fetch('/api/public/tariffs');
            const data = await res.json();
            this.tariffs = data.tariffs || [];

            container.innerHTML = this.tariffs.map(t => `
                <div class="tolk-card p-6 flex flex-col justify-between hover:border-orange-400 hover:shadow-md transition">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs font-semibold px-2.5 py-1 rounded-full ${
                                t.badge === 'Популярный' ? 'bg-orange-100 text-orange-700' :
                                t.badge === 'Пробный' ? 'bg-emerald-100 text-emerald-700' :
                                'bg-blue-100 text-blue-700'
                            }">
                                ${t.badge}
                            </span>
                            <span class="text-xs text-gray-500 font-medium">до 5 человек</span>
                        </div>
                        <h3 class="text-xl font-bold text-gray-900 mb-2">${t.name}</h3>
                        <p class="text-gray-600 text-sm mb-4 leading-relaxed">${t.description}</p>
                        
                        <div class="text-2xl font-extrabold text-orange-600 mb-4">${t.price_display}</div>
                        
                        <ul class="space-y-2 mb-6 text-sm text-gray-600">
                            ${t.features.map(f => `
                                <li class="flex items-start gap-2">
                                    <svg class="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                    <span>${f}</span>
                                </li>
                            `).join('')}
                        </ul>
                    </div>

                    <button onclick="Landing.selectTariff('${t.id}')" class="btn-primary w-full py-2.5 text-sm">
                        Записаться на курс
                    </button>
                </div>
            `).join('');

        } catch (e) {
            console.error("Failed to load tariffs", e);
            if (container) container.innerHTML = '<p class="text-red-500 text-center col-span-3">Не удалось загрузить тарифы</p>';
        }
    },

    selectTariff(tariffId) {
        const tariff = this.tariffs.find(t => t.id === tariffId);
        if (!tariff) return;

        // If user already logged in as student, pre-fill form
        const phoneInput = document.getElementById('pay-phone');
        const nameInput = document.getElementById('pay-name');
        const tgInput = document.getElementById('pay-tg');
        
        if (State.user) {
            if (phoneInput) phoneInput.value = State.user.phone || '';
            if (nameInput) nameInput.value = State.user.full_name || '';
            if (tgInput) tgInput.value = State.user.telegram_username || '';
        }

        document.getElementById('pay-tariff-name').value = tariff.name;
        document.getElementById('pay-tariff-amount').value = tariff.price;
        document.getElementById('modal-tariff-title').innerText = `${tariff.name} (${tariff.price_display})`;

        openModal('paymentModal');
    },

    setupEventListeners() {
        const paymentForm = document.getElementById('payment-submit-form');
        if (paymentForm) {
            paymentForm.onsubmit = async (e) => {
                e.preventDefault();
                await this.submitPaymentForm();
            };
        }
    },

    async submitPaymentForm() {
        const form = document.getElementById('payment-submit-form');
        const formData = new FormData(form);
        const submitBtn = document.getElementById('btn-submit-payment');

        if (!formData.get('phone')) {
            showToast("Пожалуйста, укажите номер телефона", "danger");
            return;
        }

        try {
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerText = "Отправка...";
            }

            const res = await fetch('/api/public/submit-payment', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || "Ошибка отправки чека");

            closeModal('paymentModal');
            form.reset();
            showToast(data.message, "success");

            // If user not authenticated, authenticate with this phone or suggest login
            if (!State.user) {
                const phone = formData.get('phone');
                await loginWithPhone(phone, formData.get('full_name'), formData.get('telegram_username'));
            } else if (State.user.role === 'student') {
                navigateTo('student');
            }

        } catch (err) {
            showToast(err.message, "danger");
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerText = "Отправить чек на проверку";
            }
        }
    }
};
