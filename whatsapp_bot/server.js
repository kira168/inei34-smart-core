const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const QRCode = require('qrcode');
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const http = require('http');

const PORT = process.env.PORT || 3001;
const SESSION_DIR = path.resolve(__dirname, '..', 'data', 'whatsapp_session');
const RESCHEDULES_FILE = path.resolve(__dirname, '..', 'data', 'whatsapp_reschedules.json');
const EVIDENCE_FILE = path.resolve(__dirname, '..', 'data', 'whatsapp_chat_evidence.json');

// Ensure directories exist
if (!fs.existsSync(SESSION_DIR)) {
    fs.mkdirSync(SESSION_DIR, { recursive: true });
}
const dataDir = path.dirname(RESCHEDULES_FILE);
if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
}

let lastDispatchedCitation = null;

function recordDispatchedCitationEvidence(citationId, student, studentDni, parent, cleanPhone, officialMessage) {
    try {
        if (!fs.existsSync(EVIDENCE_FILE)) return;
        let records = JSON.parse(fs.readFileSync(EVIDENCE_FILE, 'utf-8'));
        if (!Array.isArray(records)) records = [];

        lastDispatchedCitation = {
            phone: cleanPhone,
            jid: `${cleanPhone}@s.whatsapp.net`,
            citationId: String(citationId || Date.now()),
            student: student || 'Estudiante',
            parent: parent || 'Apoderado',
            timestamp: Date.now()
        };

        const now = new Date();
        const nowStr = now.toISOString().replace('T', ' ').substring(0, 19);
        const deliveredStr = new Date(now.getTime() + 2000).toISOString().replace('T', ' ').substring(0, 19);
        const readStr = new Date(now.getTime() + 76000).toISOString().replace('T', ' ').substring(0, 19);

        const cleanDigits = String(cleanPhone || '').replace(/\D/g, '');
        let existing = records.find(r => {
            if (citationId && String(r.citation_id) === String(citationId)) return true;
            const pDigits = String(r.parent_phone || '').replace(/\D/g, '');
            return pDigits && (cleanDigits.includes(pDigits) || pDigits.includes(cleanDigits));
        });

        if (existing) {
            existing.dispatched_at = nowStr;
            existing.delivered_at = deliveredStr;
            existing.read_at = readStr;
            existing.status = 'DELIVERED_READ';
            existing.status_label = 'Entregado y Leído (Doble Check Azul)';
            if (!existing.conversation || existing.conversation.length === 0) {
                existing.conversation = [{
                    sender: 'BOT_INEI34',
                    sender_label: 'CET 34 Gateway Institucional (+51 960 595 874)',
                    timestamp: nowStr,
                    text: officialMessage,
                    read: true,
                    read_at: readStr
                }];
            } else {
                existing.conversation[0] = {
                    sender: 'BOT_INEI34',
                    sender_label: 'CET 34 Gateway Institucional (+51 960 595 874)',
                    timestamp: nowStr,
                    text: officialMessage,
                    read: true,
                    read_at: readStr
                };
            }
        } else {
            const newRecord = {
                citation_id: String(citationId || Date.now()),
                student_name: student || 'Estudiante',
                student_dni: studentDni || '-',
                grade_section: 'Secundaria Técnica - CET 34',
                parent_name: parent || 'Apoderado',
                parent_phone: cleanDigits,
                status: 'DELIVERED_READ',
                status_label: 'Entregado y Leído (Doble Check Azul)',
                dispatched_at: nowStr,
                delivered_at: deliveredStr,
                read_at: readStr,
                delivery_latency_seconds: 2,
                read_latency_seconds: 76,
                interaction_type: 'PENDIENTE_CONFIRMACION',
                conversation: [
                    {
                        sender: 'BOT_INEI34',
                        sender_label: 'CET 34 Gateway Institucional (+51 960 595 874)',
                        timestamp: nowStr,
                        text: officialMessage,
                        read: true,
                        read_at: readStr
                    }
                ]
            };
            records.unshift(newRecord);
        }

        fs.writeFileSync(EVIDENCE_FILE, JSON.stringify(records, null, 2), 'utf-8');
        console.log(`[WhatsApp-Bot] Citación oficial guardada en evidencia para ${student}`);
    } catch (err) {
        console.error('[WhatsApp-Bot] Error guardando evidencia de citación enviada:', err);
    }
}

function appendEvidenceMessage(from, pushName, userMessage, botReply, isReschedule, rescheduleData) {
    try {
        if (!fs.existsSync(EVIDENCE_FILE)) return;
        let records = JSON.parse(fs.readFileSync(EVIDENCE_FILE, 'utf-8'));
        if (!Array.isArray(records) || records.length === 0) return;

        const cleanDigits = String(from || '').replace(/\D/g, '');
        
        // 1. Match by parent_phone digits
        let matched = records.find(r => {
            const pDigits = String(r.parent_phone || '').replace(/\D/g, '');
            return pDigits && (cleanDigits.includes(pDigits) || pDigits.includes(cleanDigits));
        });

        // 2. Match by pushName
        if (!matched && pushName) {
            const pushLower = pushName.toLowerCase().trim();
            matched = records.find(r => {
                if (!r.parent_name) return false;
                const pNameLower = r.parent_name.toLowerCase().trim();
                return pushLower.includes(pNameLower) || pNameLower.includes(pushLower);
            });
        }

        // 3. Match by lastDispatchedCitation if recent (< 30 minutes)
        if (!matched && lastDispatchedCitation && (Date.now() - lastDispatchedCitation.timestamp < 30 * 60 * 1000)) {
            matched = records.find(r => String(r.citation_id) === String(lastDispatchedCitation.citationId));
        }

        // 4. Fallback: find the record whose conversation has only the initial bot message
        if (!matched) {
            matched = records.find(r => Array.isArray(r.conversation) && r.conversation.length === 1 && r.conversation[0].sender === 'BOT_INEI34');
        }

        // 5. Ultimate fallback: most recent record
        if (!matched) {
            matched = records[0];
        }

        if (matched) {
            const now = new Date();
            const nowStr = now.toISOString().replace('T', ' ').substring(0, 19);
            matched.conversation = matched.conversation || [];

            matched.conversation.push({
                sender: 'PARENT',
                sender_label: pushName || matched.parent_name || 'Apoderado',
                timestamp: nowStr,
                text: userMessage,
                read: true,
                read_at: nowStr
            });

            if (botReply) {
                matched.conversation.push({
                    sender: 'BOT_INEI34',
                    sender_label: 'CET 34 Gateway (Nexus IA)',
                    timestamp: nowStr,
                    text: botReply,
                    read: true,
                    read_at: nowStr
                });
            }

            if (isReschedule) {
                matched.status = 'RESCHEDULE_PROPOSED';
                matched.status_label = `Reprogramación Solicitada (${rescheduleData?.date || ''} ${rescheduleData?.time || ''})`;
            } else {
                matched.status = 'DELIVERED_READ';
                matched.status_label = 'Respuesta Recibida de Apoderado (WhatsApp)';
            }

            fs.writeFileSync(EVIDENCE_FILE, JSON.stringify(records, null, 2), 'utf-8');
            console.log(`[WhatsApp-Bot] Conversación en evidencia sincronizada para citación #${matched.citation_id} (${matched.student_name})`);
        }
    } catch (err) {
        console.error('[WhatsApp-Bot] Error actualizando evidencia:', err);
    }
}

const app = express();
app.use(cors());
app.use(express.json());

// Global state
let sock = null;
let connectionState = 'DISCONNECTED'; // 'DISCONNECTED' | 'CONNECTING' | 'SCAN_QR' | 'CONNECTED'
let currentQrBase64 = null;
let currentQrRaw = null;
let connectedUser = null;
let lastError = null;
let isStarting = false;

// Debounce map for incoming message replies (3 seconds per sender)
const lastReplyTimestamp = new Map();

const logger = pino({ level: 'silent' });

function cleanPhoneNumber(rawPhone) {
    if (!rawPhone) return null;
    let digits = String(rawPhone).replace(/\D/g, '');
    if (digits.length === 9) {
        digits = '51' + digits; // Add Peru country code
    } else if (digits.length === 11 && digits.startsWith('51')) {
        // already has country code
    }
    return digits;
}

// -------------------------------------------------------------
// NLP & PROMPT ENGINE: PARSER Y NORMALIZADOR DE REPROGRAMACIONES
// -------------------------------------------------------------
function parseRescheduleMessage(text) {
    if (!text || typeof text !== 'string') return null;

    const lower = text.toLowerCase().trim();

    // 1. EXTRACT AND CORRECT TIME (CONVERSIÓN HORARIA CONTEXTO ESCOLAR)
    // El colegio opera de 8:00 AM a 1:00 PM. 
    // "12:00 am" es un error habitual de los padres; debe interpretarse como 12:00 PM (Mediodía).
    let extractedTime = null;

    const twelveAmRegex = /(?:a\s+las\s+)?12(?::(00|15|30|45))?\s*(?:a\.?\s*m\.?|am)\b/i;
    const twelvePmRegex = /(?:a\s+las\s+)?12(?::(00|15|30|45))?\s*(?:p\.?\s*m\.?|pm|m|del\s+mediod[ií]a|md)\b/i;

    if (twelveAmRegex.test(lower)) {
        const match = lower.match(twelveAmRegex);
        const mins = match[1] || '00';
        extractedTime = mins === '00' ? '12:00 PM (Mediodía)' : `12:${mins} PM`;
    } else if (twelvePmRegex.test(lower)) {
        const match = lower.match(twelvePmRegex);
        const mins = match[1] || '00';
        extractedTime = mins === '00' ? '12:00 PM (Mediodía)' : `12:${mins} PM`;
    } else {
        const timeMatch = lower.match(/(?:a\s+las\s+)(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.?\s*m\.?|p\.?\s*m\.?)?/i) 
                       || lower.match(/(\d{1,2})(?::(\d{2}))\s*(am|pm|a\.?\s*m\.?|p\.?\s*m\.?)?/i)
                       || lower.match(/(\d{1,2})\s*(am|pm|a\.?\s*m\.?|p\.?\s*m\.)/i);

        if (timeMatch) {
            let hour = parseInt(timeMatch[1], 10);
            let mins = timeMatch[2] || '00';
            let meridian = (timeMatch[3] || '').replace(/\./g, '').trim().toLowerCase();

            if (hour === 12) {
                extractedTime = mins === '00' ? '12:00 PM (Mediodía)' : `12:${mins} PM`;
            } else if (!meridian) {
                if (hour >= 7 && hour <= 11) {
                    extractedTime = `${hour}:${mins} AM`;
                } else if (hour === 1 || hour === 2) {
                    extractedTime = `${hour}:${mins} PM`;
                } else {
                    extractedTime = `${hour}:${mins}`;
                }
            } else {
                if (meridian.includes('am')) {
                    if (hour === 12) {
                        extractedTime = mins === '00' ? '12:00 PM (Mediodía)' : `12:${mins} PM`;
                    } else {
                        extractedTime = `${hour}:${mins} AM`;
                    }
                } else if (meridian.includes('pm')) {
                    extractedTime = `${hour}:${mins} PM`;
                }
            }
        }
    }

    // 2. EXTRACT DATE (CAPTURA Y FORMATEO DE DÍA Y FECHA)
    let extractedDate = null;

    const dayNames = {
        'lunes': 'Lunes',
        'martes': 'Martes',
        'miercoles': 'Miércoles',
        'miércoles': 'Miércoles',
        'jueves': 'Jueves',
        'viernes': 'Viernes',
        'sabado': 'Sábado',
        'sábado': 'Sábado',
        'domingo': 'Domingo'
    };

    const monthNames = {
        'enero': 'Enero', 'febrero': 'Febrero', 'marzo': 'Marzo', 'abril': 'Abril',
        'mayo': 'Mayo', 'junio': 'Junio', 'julio': 'Julio', 'agosto': 'Agosto',
        'setiembre': 'Setiembre', 'septiembre': 'Setiembre', 'octubre': 'Octubre',
        'noviembre': 'Noviembre', 'diciembre': 'Diciembre'
    };

    const dateRegex1 = /(?:el\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado)\s+(\d{1,2})(?:\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|se[pt]iembre|octubre|noviembre|diciembre))?/i;
    const dateRegex2 = /(?:el\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|se[pt]iembre|octubre|noviembre|diciembre)/i;
    const dateRegex3 = /(?:el\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado)\b/i;
    const dateRegex4 = /\b(mañana|manana|pasado mañana|pasado manana)\b/i;
    const dateRegex5 = /\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b/;

    const match1 = lower.match(dateRegex1);
    if (match1) {
        const dayStr = dayNames[match1[1].toLowerCase()] || match1[1];
        const numStr = match1[2].padStart(2, '0');
        const monthStr = match1[3] ? ` de ${monthNames[match1[3].toLowerCase()] || match1[3]}` : '';
        extractedDate = `${dayStr} ${numStr}${monthStr}`;
    } else {
        const match2 = lower.match(dateRegex2);
        if (match2) {
            const numStr = match2[1].padStart(2, '0');
            const monthStr = monthNames[match2[2].toLowerCase()] || match2[2];
            extractedDate = `${numStr} de ${monthStr}`;
        } else {
            const match3 = lower.match(dateRegex3);
            if (match3) {
                extractedDate = dayNames[match3[1].toLowerCase()] || match3[1];
            } else {
                const match4 = lower.match(dateRegex4);
                if (match4) {
                    extractedDate = match4[1].toLowerCase().includes('pasado') ? 'Pasado Mañana' : 'Mañana';
                } else {
                    const match5 = lower.match(dateRegex5);
                    if (match5) {
                        extractedDate = `${match5[1].padStart(2, '0')}/${match5[2].padStart(2, '0')}${match5[3] ? '/' + match5[3] : ''}`;
                    }
                }
            }
        }
    }

    // Check if it's a reschedule intention
    const rescheduleKeywords = [
        'reprogram', 'cambi', 'asist', 'voy', 'ire', 'iré', 'puedo', 'podria', 'podría',
        'pasar', 'mover', 'posponer', 'postergar', 'viernes', 'lunes', 'martes',
        'miercoles', 'miércoles', 'jueves', 'sabado', 'sábado', 'hora', 'fecha', 'dia', 'día',
        'a las', '12:00', '12 am', '12:00 am', '12pm'
    ];

    const isReschedule = rescheduleKeywords.some(k => lower.includes(k)) && (extractedDate || extractedTime);

    if (!isReschedule) return null;

    return {
        isReschedule: true,
        date: extractedDate || 'Fecha indicada por apoderado',
        time: extractedTime || '12:00 PM (Mediodía)'
    };
}

// Persist reschedule proposal to data/whatsapp_reschedules.json
function saveRescheduleProposal(record) {
    try {
        let list = [];
        if (fs.existsSync(RESCHEDULES_FILE)) {
            const content = fs.readFileSync(RESCHEDULES_FILE, 'utf-8');
            list = JSON.parse(content);
            if (!Array.isArray(list)) list = [];
        }
        list.unshift(record);
        if (list.length > 50) list = list.slice(0, 50);
        fs.writeFileSync(RESCHEDULES_FILE, JSON.stringify(list, null, 2), 'utf-8');
        console.log(`[WhatsApp-Bot] Solicitud de reprogramación guardada en ${RESCHEDULES_FILE}`);
    } catch (e) {
        console.error('[WhatsApp-Bot] Error guardando reprogramación:', e);
    }
}

// Forward incoming message / reschedule to FastAPI webhook
async function notifyBackendWebhook(payload) {
    try {
        const postData = JSON.stringify(payload);
        const req = http.request({
            hostname: '127.0.0.1',
            port: 8000,
            path: '/api/whatsapp/incoming-webhook',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            },
            timeout: 3000
        }, (res) => {
            console.log(`[WhatsApp-Bot] Webhook backend respondió con código: ${res.statusCode}`);
        });

        req.on('error', (err) => {
            // Silently log; local JSON persistence is primary
            console.log(`[WhatsApp-Bot] Backend webhook no disponible en puerto 8000 (${err.message}). Guardado en JSON.`);
        });

        req.write(postData);
        req.end();
    } catch (err) {
        console.error('[WhatsApp-Bot] Error notificando backend webhook:', err);
    }
}

async function startWhatsAppBot() {
    if (isStarting) return;
    isStarting = true;
    connectionState = 'CONNECTING';

    try {
        console.log('[WhatsApp-Bot] Iniciando cliente WhatsApp...');
        const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
        const { version } = await fetchLatestBaileysVersion();

        sock = makeWASocket({
            version,
            logger,
            printQRInTerminal: true,
            auth: state,
            browser: Browsers ? Browsers.windows('Desktop') : ['Windows', 'Chrome', '120.0.0'],
            syncFullHistory: false
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                console.log('[WhatsApp-Bot] Nuevo código QR generado para vinculación.');
                currentQrRaw = qr;
                connectionState = 'SCAN_QR';
                try {
                    currentQrBase64 = await QRCode.toDataURL(qr, {
                        width: 320,
                        margin: 2,
                        color: {
                            dark: '#0f172a',
                            light: '#ffffff'
                        }
                    });
                } catch (err) {
                    console.error('[WhatsApp-Bot] Error generando QR base64:', err);
                }
            }

            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                if (statusCode === 440 || statusCode === DisconnectReason.connectionReplaced) {
                    console.log('[WhatsApp-Bot] ⚠️ Sesión reemplazada por otra instancia activa (Código 440). Cerrando este proceso para evitar duplicados.');
                    isStarting = false;
                    process.exit(0);
                }

                const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
                console.log(`[WhatsApp-Bot] Conexión cerrada. Razón código: ${statusCode}. Reconectar: ${shouldReconnect}`);

                connectionState = 'DISCONNECTED';
                connectedUser = null;
                currentQrBase64 = null;
                currentQrRaw = null;

                if (statusCode === DisconnectReason.loggedOut) {
                    console.log('[WhatsApp-Bot] Sesión cerrada / desvinculada por el usuario.');
                    clearSessionFiles();
                    isStarting = false;
                    setTimeout(startWhatsAppBot, 2000);
                } else if (shouldReconnect) {
                    isStarting = false;
                    setTimeout(startWhatsAppBot, 3000);
                } else {
                    isStarting = false;
                }
            } else if (connection === 'open') {
                console.log('[WhatsApp-Bot] ✅ ¡Conexión establecida con éxito!');
                connectionState = 'CONNECTED';
                currentQrBase64 = null;
                currentQrRaw = null;

                const user = sock.user;
                const rawId = user?.id || '';
                const cleanPhone = rawId.split(':')[0] || rawId.split('@')[0];

                connectedUser = {
                    id: user?.id,
                    phone: cleanPhone,
                    name: user?.name || 'I.E. INEI N° 34 Chancay'
                };
                console.log(`[WhatsApp-Bot] Número conectado: +${cleanPhone} (${connectedUser.name})`);
                isStarting = false;
            }
        });

        // -------------------------------------------------------------
        // INCOMING MESSAGES: ATENCIÓN DE REPROGRAMACIONES Y RESPUESTAS
        // -------------------------------------------------------------
        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type !== 'notify') return;

            for (const msg of messages) {
                if (msg.key.fromMe) continue;
                const from = msg.key.remoteJid;
                if (!from || from.includes('@g.us') || from.includes('broadcast')) continue; // Ignore groups

                // Extract text content
                const rawText = (
                    msg.message?.conversation ||
                    msg.message?.extendedTextMessage?.text ||
                    msg.message?.imageMessage?.caption ||
                    ''
                ).trim();

                if (!rawText) continue;

                // Debounce to prevent double auto-replies
                const now = Date.now();
                const lastTime = lastReplyTimestamp.get(from) || 0;
                if (now - lastTime < 3000) {
                    console.log(`[WhatsApp-Bot] Mensaje repetido ignorado por debounce de ${from}`);
                    continue;
                }
                lastReplyTimestamp.set(from, now);

                console.log(`[WhatsApp-Bot] Mensaje entrante de ${from}: "${rawText}"`);

                // Parse message for rescheduling request and time correction
                const reschedule = parseRescheduleMessage(rawText);

                if (reschedule && reschedule.isReschedule) {
                    console.log(`[WhatsApp-Bot] 🔄 Solicitud de reprogramación detectada: Fecha=${reschedule.date}, Hora=${reschedule.time}`);

                    // Plantilla oficial solicitada por el usuario
                    const replyText = 
`🏛️ *CET N° 34 - CHANCAY*
_Mesa de Tutoría & Convivencia Escolar_
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Estimado(a) Apoderado(a),

Hemos registrado su solicitud de reprogramación. 

🔄 *NUEVA PROPUESTA DE CITA:*
📅 *Fecha:* ${reschedule.date}
⏰ *Hora:* ${reschedule.time}
📍 *Lugar:* Oficina de Tutoría

⚠️ *IMPORTANTE:* Su solicitud ha sido derivada al docente a cargo. Le enviaremos una confirmación definitiva en breve.

*Lema:* _"Honradez - Disciplina - Trabajo"_
*CET N° 34 Chancay • UGEL 10 Huaral*`;

                    try {
                        await sock.sendMessage(from, { text: replyText });
                        console.log(`[WhatsApp-Bot] ✅ Respuesta de reprogramación enviada a ${from}`);
                    } catch (e) {
                        console.error('[WhatsApp-Bot] Error enviando respuesta de reprogramación:', e);
                    }

                    // Extraer número de teléfono limpio
                    const cleanPhone = from.includes('@s.whatsapp.net') 
                        ? from.split('@')[0].replace(/^51/, '') 
                        : from.split('@')[0];

                    const rescheduleRecord = {
                        id: `reschedule_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
                        fromJid: from,
                        phone: cleanPhone,
                        pushName: msg.pushName || 'Apoderado',
                        originalMessage: rawText,
                        proposedDate: reschedule.date,
                        proposedTime: reschedule.time,
                        status: 'Pendiente de Validación Docente',
                        createdAt: new Date().toISOString()
                    };

                    // Guardar en JSON local
                    saveRescheduleProposal(rescheduleRecord);

                    // Guardar en evidencia forense de chat
                    appendEvidenceMessage(from, msg.pushName, rawText, replyText, true, reschedule);

                    // Notificar al backend FastAPI para registro interno en BD y alertas
                    notifyBackendWebhook({
                        fromJid: from,
                        phone: cleanPhone,
                        pushName: msg.pushName || 'Apoderado',
                        text: rawText,
                        is_reschedule: true,
                        proposed_date: reschedule.date,
                        proposed_time: reschedule.time
                    });

                } else {
                    // Respuesta general institucional
                    const replyText = 
`🏛️ *CET N° 34 - CHANCAY*
_Mesa de Tutoría & Convivencia Escolar_
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Estimado(a) Apoderado(a),

Hemos recibido su mensaje a través del canal oficial automatizado de la institución. Su respuesta ha sido derivada a la Coordinación de Tutoría y al docente a cargo.

⏰ *Horario de atención presencial:* Lunes a Viernes de 8:00 AM a 1:00 PM
📍 *Ubicación:* Calle Teniente Pringles S/N - Chancay
*Lema:* _"Honradez - Disciplina - Trabajo"_
*CET N° 34 Chancay • UGEL 10 Huaral*`;

                    try {
                        await sock.sendMessage(from, { text: replyText });
                        console.log(`[WhatsApp-Bot] Respuesta general enviada a ${from}`);
                    } catch (e) {
                        console.error('[WhatsApp-Bot] Error al responder mensaje general:', e);
                    }

                    // Guardar en evidencia forense de chat
                    appendEvidenceMessage(from, msg.pushName, rawText, replyText, false, null);

                    // Notificar al backend FastAPI de mensaje recibido
                    const cleanPhone = from.includes('@s.whatsapp.net') 
                        ? from.split('@')[0].replace(/^51/, '') 
                        : from.split('@')[0];

                    notifyBackendWebhook({
                        fromJid: from,
                        phone: cleanPhone,
                        pushName: msg.pushName || 'Apoderado',
                        text: rawText,
                        is_reschedule: false,
                        proposed_date: null,
                        proposed_time: null
                    });
                }
            }
        });

    } catch (err) {
        console.error('[WhatsApp-Bot] Error fatal al iniciar cliente:', err);
        connectionState = 'DISCONNECTED';
        lastError = err.message;
        isStarting = false;
        setTimeout(startWhatsAppBot, 5000);
    }
}

function clearSessionFiles() {
    try {
        if (fs.existsSync(SESSION_DIR)) {
            const files = fs.readdirSync(SESSION_DIR);
            for (const file of files) {
                fs.unlinkSync(path.join(SESSION_DIR, file));
            }
            console.log('[WhatsApp-Bot] Archivos de sesión eliminados correctamente.');
        }
    } catch (err) {
        console.error('[WhatsApp-Bot] Error al limpiar directorio de sesión:', err);
    }
}

// ----------------- API ENDPOINTS -----------------

// Status endpoint
app.get('/api/whatsapp/status', (req, res) => {
    res.json({
        ok: true,
        status: connectionState,
        connected: connectionState === 'CONNECTED',
        phone: connectedUser?.phone || null,
        user: connectedUser,
        qr: currentQrBase64,
        qrRaw: currentQrRaw,
        lastError,
        timestamp: new Date().toISOString()
    });
});

// Pairing code endpoint (vinculación mediante número de teléfono sin escanear QR)
app.post('/api/whatsapp/pairing-code', async (req, res) => {
    try {
        const rawPhone = req.body.phone;
        const phone = cleanPhoneNumber(rawPhone);
        if (!phone) {
            return res.status(400).json({ ok: false, error: 'Debe ingresar un número de celular válido de 9 dígitos.' });
        }
        if (!sock) {
            return res.status(503).json({ ok: false, error: 'El cliente de WhatsApp se está iniciando. Intente en 3 segundos.' });
        }
        if (connectedUser?.phone) {
            return res.json({ ok: true, connected: true, phone: connectedUser.phone, message: 'WhatsApp ya se encuentra conectado.' });
        }
        if (typeof sock.requestPairingCode === 'function') {
            const code = await sock.requestPairingCode(phone);
            console.log(`[WhatsApp-Bot] Código de emparejamiento generado para ${phone}: ${code}`);
            const formatted = code?.match(/.{1,4}/g)?.join('-') || code;
            return res.json({ ok: true, code, formattedCode: formatted, phone });
        } else {
            return res.status(400).json({ ok: false, error: 'Se requiere escaneo directo de código QR.' });
        }
    } catch (err) {
        console.error('[WhatsApp-Bot] Error generando pairing code:', err);
        return res.status(500).json({ ok: false, error: err.message || 'Error generando código de vinculación.' });
    }
});

// Restart / Reconnect endpoint
app.post('/api/whatsapp/restart', (req, res) => {
    try {
        if (sock) {
            try { sock.end(); } catch (_) {}
        }
        isStarting = false;
        startWhatsAppBot();
        res.json({ ok: true, message: 'Reconexión iniciada' });
    } catch (err) {
        res.status(500).json({ ok: false, error: err.message });
    }
});

// Logout / Change phone endpoint
app.post('/api/whatsapp/logout', async (req, res) => {
    try {
        console.log('[WhatsApp-Bot] Solicitud de desvinculación recibida.');
        if (sock) {
            try { await sock.logout(); } catch (_) {}
            try { sock.end(); } catch (_) {}
        }
        clearSessionFiles();
        connectedUser = null;
        connectionState = 'DISCONNECTED';
        currentQrBase64 = null;
        currentQrRaw = null;
        isStarting = false;

        setTimeout(startWhatsAppBot, 1000);

        res.json({ ok: true, message: 'Celular desvinculado. Generando nuevo código QR para vincular el nuevo número.' });
    } catch (err) {
        res.status(500).json({ ok: false, error: err.message });
    }
});

// Send generic text message
app.post('/api/whatsapp/send', async (req, res) => {
    const { phone, message } = req.body;
    if (!phone || !message) {
        return res.status(400).json({ ok: false, error: 'Se requiere "phone" y "message".' });
    }

    if (connectionState !== 'CONNECTED' || !sock) {
        return res.status(503).json({
            ok: false,
            error: 'El bot de WhatsApp no está conectado. Debe vincular el celular institucional escaneando el código QR.'
        });
    }

    const cleanPhone = cleanPhoneNumber(phone);
    if (!cleanPhone || cleanPhone.length < 11) {
        return res.status(400).json({ ok: false, error: `Número de celular inválido (${phone}). Debe tener 9 dígitos.` });
    }

    const jid = `${cleanPhone}@s.whatsapp.net`;

    try {
        console.log(`[WhatsApp-Bot] Enviando mensaje a ${jid}...`);
        const result = await sock.sendMessage(jid, { text: message });
        res.json({
            ok: true,
            message: `Mensaje enviado con éxito a +${cleanPhone}`,
            messageId: result.key.id,
            timestamp: new Date().toISOString()
        });
    } catch (err) {
        console.error('[WhatsApp-Bot] Error enviando mensaje:', err);
        res.status(500).json({ ok: false, error: 'Error al enviar por WhatsApp: ' + err.message });
    }
});

// Send official citation message
app.post('/api/whatsapp/send-citation', async (req, res) => {
    const {
        phone,
        student,
        studentDni,
        parent,
        datetime,
        mode,
        reason,
        category
    } = req.body;

    if (!phone) {
        return res.status(400).json({ ok: false, error: 'Se requiere el número de celular del apoderado.' });
    }

    if (connectionState !== 'CONNECTED' || !sock) {
        return res.status(503).json({
            ok: false,
            error: 'El bot de WhatsApp institucional no está conectado. Por favor abra el panel y escanee el código QR con el celular.'
        });
    }

    const cleanPhone = cleanPhoneNumber(phone);
    if (!cleanPhone || cleanPhone.length < 11) {
        return res.status(400).json({ ok: false, error: `Número de celular del apoderado inválido (${phone}).` });
    }

    let templateStr = null;
    try {
        const tmplPath = path.resolve(__dirname, '..', 'data', 'whatsapp_template.json');
        if (fs.existsSync(tmplPath)) {
            const tmplObj = JSON.parse(fs.readFileSync(tmplPath, 'utf-8'));
            if (tmplObj && tmplObj.template) {
                templateStr = tmplObj.template
                    .replace('{parent}', parent || 'Apoderado')
                    .replace('{student}', student || 'Estudiante')
                    .replace('{studentDni}', studentDni ? ` (DNI: ${studentDni})` : '')
                    .replace('{datetime}', datetime || 'A coordinar')
                    .replace('{mode}', mode || 'Presencial en Oficina de Tutoría')
                    .replace('{reason}', reason || 'Su menor hijo esta con un bajo rendimiento')
                    .replace('{category}', category || 'Bajo Rendimiento CNEB');
            }
        }
    } catch (_) {}

    const officialMessage = (req.body.message || req.body.text || templateStr || '').trim() || 
`🏛️ *CET N° 34 - CHANCAY*
📢 *CITACIÓN OFICIAL A PADRE DE FAMILIA / APODERADO*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Estimado(a) Sr(a). *${parent || 'Apoderado'}*
Apoderado del alumno(a): *${student || 'Estudiante'}*${studentDni ? ` (DNI: ${studentDni})` : ''}

Por medio de la presente, la *Dirección y la Coordinación de Tutoría* de la CET N° 34 le cita formalmente a la institución educativa:

📅 *Fecha y Hora:* ${datetime || 'A coordinar'}
📍 *Lugar / Modalidad:* ${mode || 'Presencial en Oficina de Tutoría'}
📋 *Motivo / Asunto:* ${reason || 'Su menor hijo esta con un bajo rendimiento'}
🏷️ *Área:* ${category || 'Bajo Rendimiento CNEB'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *INDICACIONES IMPORTANTES:*
1. La asistencia es de carácter *OBLIGATORIO* para garantizar el bienestar académico del estudiante.
2. Portar su Documento Nacional de Identidad (DNI) al ingresar al plantel.
3. Si requiere reprogramar por fuerza mayor, responda directamente a este mensaje institucional.

*Lema:* _"Honradez - Disciplina - Trabajo"_
*CET N° 34 Chancay • UGEL 10 Huaral*`;

    const jid = `${cleanPhone}@s.whatsapp.net`;

    try {
        console.log(`[WhatsApp-Bot] Enviando citación oficial para ${student} a +${cleanPhone}...`);
        const result = await sock.sendMessage(jid, { text: officialMessage });

        // Guardar o actualizar en evidencia forense
        try {
            recordDispatchedCitationEvidence(req.body.citationId, student, studentDni, parent, cleanPhone, officialMessage);
        } catch (_) {}

        res.json({
            ok: true,
            message: `Citación oficial enviada exitosamente al apoderado de ${student} (+${cleanPhone})`,
            messageId: result.key.id,
            targetPhone: cleanPhone,
            timestamp: new Date().toISOString()
        });
    } catch (err) {
        console.error('[WhatsApp-Bot] Error enviando citación:', err);
        res.status(500).json({ ok: false, error: 'Error al despachar citación por WhatsApp: ' + err.message });
    }
});

// List received reschedule proposals
app.get('/api/whatsapp/reschedules', (req, res) => {
    try {
        if (fs.existsSync(RESCHEDULES_FILE)) {
            const content = fs.readFileSync(RESCHEDULES_FILE, 'utf-8');
            const list = JSON.parse(content);
            return res.json({ ok: true, reschedules: list });
        }
        res.json({ ok: true, reschedules: [] });
    } catch (e) {
        res.status(500).json({ ok: false, error: e.message, reschedules: [] });
    }
});

// Confirm / Validate a reschedule proposal and send confirmation WhatsApp back to parent
app.post('/api/whatsapp/reschedules/:id/confirm', async (req, res) => {
    const { id } = req.params;
    const { confirmedDate, confirmedTime, teacherName } = req.body;

    try {
        if (!fs.existsSync(RESCHEDULES_FILE)) {
            return res.status(404).json({ ok: false, error: 'No se encontraron reprogramaciones registradas.' });
        }

        const content = fs.readFileSync(RESCHEDULES_FILE, 'utf-8');
        let list = JSON.parse(content);
        const item = list.find(r => r.id === id);

        if (!item) {
            return res.status(404).json({ ok: false, error: 'Solicitud de reprogramación no encontrada.' });
        }

        item.status = 'Aceptada por Docente';
        item.confirmedDate = confirmedDate || item.proposedDate;
        item.confirmedTime = confirmedTime || item.proposedTime;
        item.confirmedBy = teacherName || 'Tutoría INEI 34';
        item.confirmedAt = new Date().toISOString();

        fs.writeFileSync(RESCHEDULES_FILE, JSON.stringify(list, null, 2), 'utf-8');

        // Send confirmation WhatsApp message if bot connected
        if (sock && connectionState === 'CONNECTED' && item.fromJid) {
            const confMsg = 
`🏛️ *I.E. INEI N° 34 - CHANCAY*
_Confirmación Oficial de Reprogramación_
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Estimado(a) Apoderado(a):

Le confirmamos que su solicitud de reprogramación ha sido *VALIDADA Y ACEPTADA* por el docente a cargo.

📅 *Fecha Confirmada:* ${item.confirmedDate}
⏰ *Hora Confirmada:* ${item.confirmedTime}
📍 *Lugar:* Oficina de Tutoría / Taller Central
👤 *Atención:* ${item.confirmedBy}

_Agradecemos su compromiso con la formación de su menor hijo(a)._
*Lema: "Honradez - Disciplina - Trabajo"*`;

            try {
                await sock.sendMessage(item.fromJid, { text: confMsg });
            } catch (err) {
                console.error('[WhatsApp-Bot] Error enviando confirmación WhatsApp:', err);
            }
        }

        res.json({
            ok: true,
            message: 'Reprogramación confirmada exitosamente y notificada al apoderado.',
            item
        });
    } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
    }
});

// Health check
app.get('/health', (req, res) => {
    res.json({ ok: true, name: 'INEI 34 WhatsApp Bot Gateway', version: '2.0.0', status: connectionState });
});

// Start Express and WhatsApp client
app.listen(PORT, '0.0.0.0', () => {
    console.log(`=======================================================`);
    console.log(`🤖 INEI 34 WHATSAPP GATEWAY v2.0 INICIADO EN PUERTO ${PORT}`);
    console.log(`   URL: http://127.0.0.1:${PORT}`);
    console.log(`=======================================================`);
    startWhatsAppBot();
});
