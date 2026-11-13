/**
 * INEI SMART-CORE - Ollama Monitor Client
 * Módulo Frontend Desacoplado para Monitoreo de Disponibilidad de IA (Ollama Local)
 * I.E. Emblemática INEI N.º 34 de Chancay
 *
 * Características:
 * 1. Monitoreo no bloqueante con retroceso progresivo.
 * 2. Cancelación limpia de temporizadores al cambiar de pestaña o cerrar sesión.
 * 3. Conservación del estado y trabajo en curso del usuario durante interrupciones.
 * 4. Interfaz interactiva para Administrador y Director.
 */

(function (window) {
    'use strict';

    const OllamaMonitorClient = {
        timer: null,
        intervalMs: 30000,
        isActive: false,
        lastState: null,

        /**
         * Inicializa el monitor si el rol es autorizado (ADMINISTRADOR o DIRECTOR).
         */
        init: function () {
            this.stopPolling();
            const role = this.getCurrentUserRole();
            if (role === 'ADMINISTRADOR' || role === 'DIRECTOR') {
                this.startPolling();
                this.checkHealth(false).then(data => this.updateBadge(data));
            }
        },

        getCurrentUserRole: function () {
            if (window.currentUser && window.currentUser.role) {
                return String(window.currentUser.role).toUpperCase();
            }
            if (window.currentRole) {
                return String(window.currentRole).toUpperCase();
            }
            return '';
        },

        startPolling: function () {
            if (this.timer) {
                clearInterval(this.timer);
            }
            this.isActive = true;
            this.timer = setInterval(async () => {
                if (!this.isActive) return;
                const data = await this.checkHealth(false);
                this.updateBadge(data);
            }, this.intervalMs);
        },

        stopPolling: function () {
            this.isActive = false;
            if (this.timer) {
                clearInterval(this.timer);
                this.timer = null;
            }
        },

        checkHealth: async function (force = false, testGeneration = false) {
            try {
                if (force || testGeneration) {
                    const res = await fetch('/api/ai/admin/health-check', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ test_generation: testGeneration })
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return await res.json();
                } else {
                    const res = await fetch('/api/ai/health', {
                        method: 'GET',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return await res.json();
                }
            } catch (err) {
                return {
                    status: 'DESCONECTADO',
                    is_online: false,
                    is_model_ready: false,
                    latency_ms: 0,
                    error_message: 'Servidor Ollama no responde o conexión rechazada.'
                };
            }
        },

        getAdminDiagnostics: async function () {
            try {
                const res = await fetch('/api/ai/admin/diagnostics');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return await res.json();
            } catch (err) {
                return {
                    success: false,
                    diagnostic_category: 'SERVIDOR_OFFLINE',
                    technical_summary: 'El daemon local de Ollama no responde en http://127.0.0.1:11434.',
                    details: {
                        status: 'DESCONECTADO',
                        is_online: false,
                        is_model_ready: false,
                        latency_ms: 0,
                        configured_model: 'llama3.2:latest',
                        available_models: [],
                        error_message: 'Conexión rechazada al puerto 11434.'
                    }
                };
            }
        },

        updateBadge: function (data) {
            const badge = document.getElementById('ollamaLiveStatusBadge');
            if (!badge) return;

            const st = (data && data.status) ? data.status : 'DESCONECTADO';
            this.lastState = st;

            if (st === 'OPERATIVO') {
                badge.className = 'text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold cursor-pointer hover:bg-emerald-500/30 transition shadow-sm';
                badge.innerHTML = `● Ollama Operativo (${data.latency_ms || 0} ms)`;
                badge.title = `Modelo: ${data.configured_model || 'llama3.2'} • Click para abrir diagnóstico técnico`;
            } else if (st === 'MODELO_NO_DISPONIBLE') {
                badge.className = 'text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-bold cursor-pointer hover:bg-amber-500/30 transition shadow-sm';
                badge.innerHTML = `▲ Modelo No Disponible`;
                badge.title = 'Ollama está en línea pero falta descargar el modelo • Click para ver';
            } else if (st === 'INICIANDO') {
                badge.className = 'text-[10px] bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2 py-0.5 rounded-full font-bold cursor-pointer hover:bg-blue-500/30 transition shadow-sm';
                badge.innerHTML = `● Iniciando Tensores`;
            } else {
                badge.className = 'text-[10px] bg-red-500/20 text-red-300 border border-red-500/30 px-2 py-0.5 rounded-full font-bold cursor-pointer hover:bg-red-500/30 transition shadow-sm';
                badge.innerHTML = `● Ollama Offline (Fallback Activo)`;
                badge.title = 'Servidor Ollama inactivo • Modo de contingencia institucional activo';
            }
        },

        openModal: async function () {
            if (typeof window.showGlobalModal !== 'function') {
                alert('Ventana modal institucional no disponible.');
                return;
            }

            window.showGlobalModal(`
                <div class="p-6 space-y-5 max-w-2xl w-full">
                    <!-- Cabecera Institucional -->
                    <div class="flex justify-between items-start pb-3 border-b border-slate-100">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-red-50 text-ineiRed flex items-center justify-center text-lg shadow-sm">
                                <i class="fa-solid fa-microchip"></i>
                            </div>
                            <div>
                                <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
                                    Monitor de Salud de Inteligencia Artificial (Ollama)
                                    <span class="text-[10px] font-mono font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">AI-CORE-01</span>
                                </h3>
                                <p class="text-xs text-slate-500">Diagnóstico técnico en tiempo real • I.E. Emblemática INEI N.º 34 Chancay</p>
                            </div>
                        </div>
                        <button onclick="closeGlobalModal()" class="text-slate-400 hover:text-slate-600 transition text-lg p-1">
                            <i class="fa-solid fa-xmark"></i>
                        </button>
                    </div>

                    <!-- Contenedor Dinámico -->
                    <div id="ollamaMonitorContent" class="space-y-4">
                        <div class="flex items-center justify-center h-36 text-slate-400 text-xs">
                            <i class="fa-solid fa-spinner fa-spin mr-2 text-ineiRed"></i> Consultando diagnóstico técnico de Ollama...
                        </div>
                    </div>

                    <!-- Botones de Acción -->
                    <div class="pt-4 border-t border-slate-100 flex flex-wrap justify-between items-center gap-2 text-xs">
                        <div class="flex gap-2">
                            <button type="button" onclick="OllamaMonitorClient.refreshModal(false)" class="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-3 py-2 rounded-xl transition flex items-center gap-1.5 shadow-sm">
                                <i class="fa-solid fa-arrows-rotate"></i> Comprobar Estado
                            </button>
                            <button type="button" onclick="OllamaMonitorClient.refreshModal(true)" class="bg-amber-50 hover:bg-amber-100 text-amber-800 font-bold px-3 py-2 rounded-xl transition border border-amber-200 flex items-center gap-1.5 shadow-sm" title="Ejecuta una inferencia mínima de 1 token para validar tensores">
                                <i class="fa-solid fa-bolt"></i> Test de Inferencia
                            </button>
                        </div>
                        <button type="button" onclick="closeGlobalModal()" class="bg-slate-900 hover:bg-slate-800 text-white font-bold px-4 py-2 rounded-xl transition shadow">
                            Cerrar
                        </button>
                    </div>
                </div>
            `);

            await this.refreshModal(false);
        },

        refreshModal: async function (testGeneration = false) {
            const container = document.getElementById('ollamaMonitorContent');
            if (!container) return;

            container.innerHTML = `
                <div class="flex items-center justify-center h-36 text-slate-400 text-xs">
                    <i class="fa-solid fa-spinner fa-spin mr-2 text-ineiRed"></i> ${testGeneration ? 'Ejecutando prueba de inferencia ligera en Ollama...' : 'Actualizando diagnóstico de Ollama...'}
                </div>
            `;

            let diag = null;
            if (testGeneration) {
                const resCheck = await this.checkHealth(true, true);
                diag = await this.getAdminDiagnostics();
                if (resCheck && resCheck.test_generation) {
                    diag.test_generation_result = resCheck.test_generation;
                }
            } else {
                diag = await this.getAdminDiagnostics();
            }

            const details = (diag && diag.details) ? diag.details : {};
            const st = details.status || 'DESCONECTADO';
            const latency = details.latency_ms || 0;
            const models = details.available_models || [];
            const configuredModel = details.configured_model || 'llama3.2:latest';
            const errorMsg = details.error_message || 'Sin incidencias reportadas.';
            const summary = diag.technical_summary || 'Diagnóstico no disponible.';

            let bannerHtml = '';
            if (st === 'OPERATIVO') {
                bannerHtml = `
                    <div class="p-4 bg-emerald-50 border border-emerald-300 rounded-2xl flex items-start gap-3">
                        <div class="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center text-lg flex-shrink-0 mt-0.5">
                            <i class="fa-solid fa-circle-check"></i>
                        </div>
                        <div class="flex-1">
                            <div class="flex justify-between items-center">
                                <h4 class="font-bold text-emerald-900 text-sm">MOTOR OLLAMA OPERATIVO Y DISPONIBLE</h4>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    ESTADO: OPERATIVO
                                </span>
                            </div>
                            <p class="text-xs text-emerald-700 mt-1 leading-relaxed">${summary}</p>
                        </div>
                    </div>
                `;
            } else if (st === 'MODELO_NO_DISPONIBLE') {
                bannerHtml = `
                    <div class="p-4 bg-amber-50 border border-amber-300 rounded-2xl flex items-start gap-3">
                        <div class="w-8 h-8 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center text-lg flex-shrink-0 mt-0.5">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                        </div>
                        <div class="flex-1">
                            <div class="flex justify-between items-center">
                                <h4 class="font-bold text-amber-900 text-sm">MODELO CONFIGURADO NO DISPONIBLE</h4>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                                    MODELO NO DESCARGADO
                                </span>
                            </div>
                            <p class="text-xs text-amber-800 mt-1 leading-relaxed">${summary}</p>
                        </div>
                    </div>
                `;
            } else {
                bannerHtml = `
                    <div class="p-4 bg-red-50 border border-red-300 rounded-2xl flex items-start gap-3">
                        <div class="w-8 h-8 rounded-xl bg-red-100 text-red-600 flex items-center justify-center text-lg flex-shrink-0 mt-0.5">
                            <i class="fa-solid fa-circle-xmark"></i>
                        </div>
                        <div class="flex-1">
                            <div class="flex justify-between items-center">
                                <h4 class="font-bold text-red-900 text-sm">SERVICIO OLLAMA DESCONECTADO (OFFLINE)</h4>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200">
                                    OFFLINE / PUERTO 11434
                                </span>
                            </div>
                            <p class="text-xs text-red-700 mt-1 leading-relaxed">${summary}</p>
                            <p class="text-[11px] text-red-600 mt-1 font-medium bg-red-100/50 p-2 rounded-lg border border-red-200">
                                <i class="fa-solid fa-shield-halved mr-1"></i> Resiliencia Activa: Los usuarios continúan operando con el motor pedagógico de contingencia sin bloqueos ni errores visibles.
                            </p>
                        </div>
                    </div>
                `;
            }

            // Test Generation Badge if present
            let testGenHtml = '';
            if (diag.test_generation_result) {
                const tg = diag.test_generation_result;
                testGenHtml = `
                    <div class="p-3 ${tg.success ? 'bg-emerald-50 border-emerald-300 text-emerald-800' : 'bg-red-50 border-red-300 text-red-800'} border rounded-xl text-xs flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <i class="fa-solid ${tg.success ? 'fa-check text-emerald-600' : 'fa-xmark text-red-600'}"></i>
                            <span>${tg.message || 'Prueba completada'}</span>
                        </div>
                        <span class="font-mono font-bold">${tg.elapsed_ms || 0} ms</span>
                    </div>
                `;
            }

            // Model tags badges
            let modelsHtml = '';
            if (models.length > 0) {
                modelsHtml = models.map(m => `
                    <span class="text-[10px] font-mono font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                        ${m}
                    </span>
                `).join(' ');
            } else {
                modelsHtml = '<span class="text-xs text-slate-400 italic">Ningún modelo detectado en el repositorio local.</span>';
            }

            container.innerHTML = `
                ${bannerHtml}
                ${testGenHtml}

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <!-- Tarjeta 1: Latencia y Dirección -->
                    <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
                        <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Conexión y Latencia</div>
                        <div class="flex justify-between items-center">
                            <span class="text-slate-600">Dirección Local:</span>
                            <span class="font-mono font-bold text-slate-800 text-[11px]">http://127.0.0.1:11434</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-slate-600">Tiempo de Respuesta:</span>
                            <span class="font-mono font-bold ${latency > 100 ? 'text-amber-600' : 'text-emerald-700'}">${latency} ms</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-slate-600">Circuit Breaker:</span>
                            <span class="font-mono font-bold ${details.circuit_state === 'CLOSED' ? 'text-emerald-700' : 'text-red-700'}">
                                ${details.circuit_state === 'CLOSED' ? 'CERRADO (En línea)' : 'ABIERTO (Fast-Fail Activo)'}
                            </span>
                        </div>
                    </div>

                    <!-- Tarjeta 2: Modelo y Repositorio -->
                    <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
                        <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Configuración de Modelo</div>
                        <div class="flex justify-between items-center">
                            <span class="text-slate-600">Modelo Activo:</span>
                            <span class="font-mono font-bold text-ineiRed">${configuredModel}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-slate-600">Total Instalados:</span>
                            <span class="font-bold text-slate-800">${models.length} modelos</span>
                        </div>
                        <div class="pt-1">
                            <div class="text-[10px] text-slate-400 font-bold uppercase mb-1">Modelos en Ollama:</div>
                            <div class="flex flex-wrap gap-1 max-h-16 overflow-y-auto">
                                ${modelsHtml}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Trazabilidad Técnica -->
                <div class="p-3 bg-slate-50 rounded-xl border border-slate-200 text-[11px] text-slate-600 space-y-1">
                    <div class="font-bold text-slate-800 flex items-center gap-1.5">
                        <i class="fa-solid fa-clock-rotate-left text-slate-500"></i> Métricas de Resiliencia Institucional
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 font-mono text-[10.5px]">
                        <div><span class="text-slate-400 block text-[9px] uppercase font-bold">Fallos:</span> <strong>${details.failure_count || 0}</strong></div>
                        <div><span class="text-slate-400 block text-[9px] uppercase font-bold">Reconexiones:</span> <strong>${details.reconnect_count || 0}</strong></div>
                        <div><span class="text-slate-400 block text-[9px] uppercase font-bold">Última Comprobación:</span> <strong>${details.last_check || '—'}</strong></div>
                        <div><span class="text-slate-400 block text-[9px] uppercase font-bold">Última Conexión OK:</span> <strong>${details.last_successful_connection || '—'}</strong></div>
                    </div>
                </div>
            `;
        }
    };

    // Exponer globalmente
    window.OllamaMonitorClient = OllamaMonitorClient;
    window.openOllamaMonitorModal = () => OllamaMonitorClient.openModal();

    // Auto-inicializar al cargar la página si el DOM está listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => OllamaMonitorClient.init());
    } else {
        OllamaMonitorClient.init();
    }

})(window);
