// utils.js - Funções de data/hora com suporte a fuso horário

// Configuração global do fuso horário
let configTimezone = {
    offset: 0,
    daylight_saving: 'auto',
    time_format: '24h'
};

// ============================================================
// FUNÇÕES DE CARREGAMENTO DA CONFIGURAÇÃO
// ============================================================

async function carregarConfigTimezone() {
    try {
        const response = await fetch('/api/config/timezone');
        if (response.ok) {
            configTimezone = await response.json();
            console.log('🌍 Fuso horário carregado:', configTimezone);
        } else {
            console.log('⚠️ Usando configuração padrão (UTC+0, 24h)');
        }
    } catch(e) {
        console.log('⚠️ Erro ao carregar fuso horário, usando padrão');
    }
}

// ============================================================
// FUNÇÕES DE CÁLCULO DE HORÁRIO DE VERÃO
// ============================================================

function isDaylightSaving(date) {
    // Verifica se está em horário de verão no hemisfério norte
    const jan = new Date(date.getFullYear(), 0, 1);
    const jul = new Date(date.getFullYear(), 6, 1);
    const offset = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());
    return date.getTimezoneOffset() < offset;
}

// ============================================================
// FUNÇÕES DE OBTENÇÃO DE DATA/HORA COM FUSO
// ============================================================

function obterDataAtual() {
    const agora = new Date();
    const offsetHoras = configTimezone.offset || 0;
    
    // Calcular horário de verão
    let dst = 0;
    if (configTimezone.daylight_saving === 'on') {
        dst = 1;
    } else if (configTimezone.daylight_saving === 'off') {
        dst = 0;
    } else if (configTimezone.daylight_saving === 'auto') {
        dst = isDaylightSaving(agora) ? 1 : 0;
    }
    
    const totalOffset = offsetHoras + dst;
    
    // Aplicar offset
    const dataAjustada = new Date(agora.getTime() + (agora.getTimezoneOffset() * 60000) + (totalOffset * 3600000));
    
    const ano = dataAjustada.getUTCFullYear();
    const mes = String(dataAjustada.getUTCMonth() + 1).padStart(2, '0');
    const dia = String(dataAjustada.getUTCDate()).padStart(2, '0');
    
    return `${ano}-${mes}-${dia}`;
}

function obterHoraAtual() {
    const agora = new Date();
    const offsetHoras = configTimezone.offset || 0;
    
    let dst = 0;
    if (configTimezone.daylight_saving === 'on') {
        dst = 1;
    } else if (configTimezone.daylight_saving === 'off') {
        dst = 0;
    } else if (configTimezone.daylight_saving === 'auto') {
        dst = isDaylightSaving(agora) ? 1 : 0;
    }
    
    const totalOffset = offsetHoras + dst;
    const dataAjustada = new Date(agora.getTime() + (agora.getTimezoneOffset() * 60000) + (totalOffset * 3600000));
    
    let horas = dataAjustada.getUTCHours();
    const minutos = String(dataAjustada.getUTCMinutes()).padStart(2, '0');
    
    // Verificar formato 12h/24h
    if (configTimezone.time_format === '12h') {
        const ampm = horas >= 12 ? 'PM' : 'AM';
        let hora12 = horas % 12;
        if (hora12 === 0) hora12 = 12;
        return `${hora12}:${minutos} ${ampm}`;
    }
    
    // Formato 24h
    return `${String(horas).padStart(2, '0')}:${minutos}`;
}

function obterDataHoraAtual() {
    return `${obterDataAtual()}T${obterHoraAtual().split(' ')[0]}`;
}

// ============================================================
// FUNÇÕES DE FORMATAÇÃO E CÁLCULO (já existentes, mantidas)
// ============================================================

function calcularDuracao(inicio, fim) {
    if (!inicio || !fim) return '';
    const inicioDate = new Date(inicio);
    const fimDate = new Date(fim);
    if (isNaN(inicioDate) || isNaN(fimDate) || fimDate <= inicioDate) return '';
    const diffMs = fimDate - inicioDate;
    const diffHoras = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutos = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    if (diffHoras > 0 && diffMinutos > 0) return `${diffHoras}h ${diffMinutos}m`;
    if (diffHoras > 0) return `${diffHoras}h`;
    if (diffMinutos > 0) return `${diffMinutos}m`;
    return '< 1m';
}

function calcularTempoEntre(dataInicio, dataFim) {
    if (!dataInicio || !dataFim) return '---';
    const inicio = new Date(dataInicio);
    const fim = new Date(dataFim);
    if (isNaN(inicio) || isNaN(fim) || fim <= inicio) return '---';
    const diffMs = fim - inicio;
    const diffHoras = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutos = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    if (diffHoras > 0 && diffMinutos > 0) return `${diffHoras}h ${diffMinutos}m`;
    if (diffHoras > 0) return `${diffHoras}h`;
    if (diffMinutos > 0) return `${diffMinutos}m`;
    return '< 1m';
}

function formatarDataHoraParaDisplay(dataHora) {
    if (!dataHora) return '-';
    const partes = dataHora.split('T');
    const data = partes[0];
    let hora = partes[1] ? partes[1].substring(0, 5) : '';
    
    if (configTimezone.time_format === '12h' && hora) {
        let [horas, minutos] = hora.split(':');
        let horaNum = parseInt(horas);
        let ampm = horaNum >= 12 ? 'PM' : 'AM';
        let hora12 = horaNum % 12 || 12;
        return `${data} ${hora12}:${minutos} ${ampm}`;
    }
    
    return `${data} ${hora}`;
}