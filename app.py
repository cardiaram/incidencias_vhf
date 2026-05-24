# app.py - Servidor completo para gestão de incidencias VHF (VERSIÓN CORREGIDA)
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import json
import os
import re
import secrets
from datetime import datetime
import threading
import webbrowser
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# ============================================================
# CONFIGURACIÓN SEGURA (desde variables de entorno)
# ============================================================
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.serviciodecorreo.es')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = SMTP_USER
FROM_NAME = os.getenv('FROM_NAME', 'Sistema de Gestão de Incidentes VHF')

# ============================================================
# ARCHIVOS DE DATOS
# ============================================================
DATA_FILE = os.path.join('data', 'incidencias.json')
CONFIG_FILE = os.path.join('data', 'config.json')
PORT = 8080
HOST = '0.0.0.0'

os.makedirs('data', exist_ok=True)

# ============================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================

def is_valid_email(email):
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_emails(email_list):
    """Valida una lista de emails"""
    if not isinstance(email_list, list):
        return False
    return all(is_valid_email(email) for email in email_list)

# ============================================================
# FUNCIONES DE CONFIGURACIÓN
# ============================================================

def ler_config():
    """Lee configuración con manejo de errores mejorado"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'stations' not in config:
                    config['stations'] = get_default_stations()
                    guardar_config(config)
                if 'timezone' not in config:
                    config['timezone'] = {'offset': 0, 'daylight_saving': 'auto', 'time_format': '24h'}
                    guardar_config(config)
                if 'smtp' not in config:
                    config['smtp'] = {
                        'server': SMTP_SERVER,
                        'port': SMTP_PORT,
                        'security': 'TLS',
                        'username': SMTP_USER,
                        'from_name': FROM_NAME
                    }
                    guardar_config(config)
                return config
    except json.JSONDecodeError as e:
        print(f"❌ Error al leer JSON: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
    
    config_padrao = {
        "users": {
            "admin": {
                "password": generate_password_hash(os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin2025')),
                "role": "admin",
                "name": "Administrador"
            },
            "lacv": {
                "password": generate_password_hash(os.getenv('DEFAULT_LACV_PASSWORD', 'lacv2025')),
                "role": "operador",
                "name": "Operador LACV"
            },
            "inco": {
                "password": generate_password_hash(os.getenv('DEFAULT_INCO_PASSWORD', 'inco2025')),
                "role": "tecnico",
                "name": "Técnico INCO"
            }
        },
        "emails": {
            "novo_incidente": ["carlos.diaz@incoengenheiros.com", "victor.argibay@incoengenheiros.com"],
            "atualizacao": ["carlos.diaz@incoengenheiros.com", "victor.argibay@incoengenheiros.com"],
            "fechamento": ["carlos.diaz@incoengenheiros.com", "victor.argibay@incoengenheiros.com"],
            "solicitacao_acesso": ["carlos.diaz@incoengenheiros.com", "victor.argibay@incoengenheiros.com"],
            "solicitacao_viagem": ["carlos.diaz@incoengenheiros.com", "victor.argibay@incoengenheiros.com"]
        },
        "stations": get_default_stations(),
        "timezone": {"offset": 0, "daylight_saving": "auto", "time_format": "24h"},
        "smtp": {
            "server": SMTP_SERVER,
            "port": SMTP_PORT,
            "security": "TLS",
            "username": SMTP_USER,
            "from_name": FROM_NAME
        }
    }
    guardar_config(config_padrao)
    return config_padrao

def guardar_config(config):
    """Guarda configuración con manejo de errores"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"❌ Error al guardar configuración: {e}")
        return False

def get_default_stations():
    return [
        {"id": 1, "name": "CCO Praia - Posto Operador", "type": "operador", "active": True},
        {"id": 2, "name": "Praia - Estação Remota (Aeroporto Nelson Mandela)", "type": "remota", "active": True},
        {"id": 3, "name": "Fogo - São Filipe", "type": "remota", "active": True},
        {"id": 4, "name": "São Vicente - Cesária Évora", "type": "remota", "active": True},
        {"id": 5, "name": "São Nicolau - Preguiça", "type": "remota", "active": True},
        {"id": 6, "name": "Sal - Amílcar Cabral", "type": "remota", "active": True},
        {"id": 7, "name": "Boa Vista - Aristides Pereira", "type": "remota", "active": True}
    ]
    
# ============================================================
# DECORADORES DE AUTENTICACIÓN
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login_page'))
            config = ler_config()
            user = config['users'].get(session['username'])
            if not user or user.get('role') not in roles:
                return "Acesso negado. Você não tem permissão.", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_emails_destino(tipo):
    config = ler_config()
    emails = config.get('emails', {}).get(tipo, [])
    # Validar emails
    if validate_emails(emails):
        return emails
    print(f"⚠️ Emails inválidos para tipo {tipo}")
    return []

# ============================================================
# FUNCIÓN PARA ENVIAR CORREO
# ============================================================

def enviar_correo(tipo, asunto, corpo_texto, logo_path=None):
    config = ler_config()
    smtp_cfg = config.get('smtp', {})
    
    servidor = smtp_cfg.get('server', SMTP_SERVER)
    porta = smtp_cfg.get('port', SMTP_PORT)
    usuario = smtp_cfg.get('username', SMTP_USER)
    senha = os.getenv('SMTP_PASSWORD', '')
    nome_remetente = smtp_cfg.get('from_name', FROM_NAME)
    
    destinatarios = get_emails_destino(tipo)
    if not destinatarios:
        print(f"⚠️ Nenhum destinatário configurado para {tipo}")
        return False
    
    try:
        print(f"\n📧 Enviando correio...")
        print(f"   Tipo: {tipo}")
        print(f"   Destinatários: {', '.join(destinatarios)}")
        
        msg = MIMEMultipart()
        msg['Subject'] = asunto
        msg['From'] = f"{nome_remetente} <{usuario}>"
        msg['To'] = ', '.join(destinatarios)
        msg.attach(MIMEText(corpo_texto, 'plain', 'utf-8'))
        
        if logo_path and os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as f:
                    logo = MIMEImage(f.read())
                    logo.add_header('Content-ID', '<logo>')
                    msg.attach(logo)
            except Exception as e:
                print(f"   ⚠️ Não foi possível anexar logo: {e}")
        
        if smtp_cfg.get('security') == 'SSL':
            server = smtplib.SMTP_SSL(servidor, porta, timeout=60)
        else:
            server = smtplib.SMTP(servidor, porta, timeout=60)
            server.starttls()
        
        server.ehlo()
        server.login(usuario, senha)
        server.sendmail(usuario, destinatarios, msg.as_string())
        server.quit()
        
        print(f"   ✅ CORREIO ENVIADO")
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"   ❌ Error de autenticación SMTP")
        return False
    except smtplib.SMTPException as e:
        print(f"   ❌ Error SMTP: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

# ============================================================
# GERADOR DE CORREIO COMPLETO
# ============================================================

def gerar_correo_incidencia(inc, tipo='criacao'):
    data = datetime.now().strftime('%d/%m/%Y %H:%M:%S UTC')
    inc_id = inc.get('id', 'N/A')
    estado = inc.get('estado', 'Ativa')
    operador = inc.get('operadorLACV', '-')
    data_deteccao = inc.get('fechaDeteccion', '-')
    estacao = inc.get('estacion', '-')
    
    # CORREGIDO: Usar consistentemente 'classificacao' (portugués)
    clas_valor = inc.get('classificacao', '')
    if clas_valor in ['Crítica', 'Alta', 'ALTA']:
        classificacao = '🔴 ALTA'
    else:
        classificacao = '🟢 BAIXA'
    
    sintomas = ', '.join(inc.get('sintomas', [])) or 'Nenhum'
    descricao = inc.get('descricao', '-')
    tecnico = inc.get('tecnicoINCO', '-')
    hora_contato = inc.get('horaContactoINCO', '-')
    
    remoto_inicio = inc.get('remoto', {}).get('inicio', '-')
    remoto_fim = inc.get('remoto', {}).get('fim', '-')
    remoto_duracao = inc.get('remoto', {}).get('duracao', '-')
    remoto_resolvido = '✅ Sim' if inc.get('remoto', {}).get('resolvida') == 'Si' else '❌ Não'
    remoto_obs = inc.get('remoto', {}).get('obs', '-')
    
    presencial_chegada = inc.get('presencial', {}).get('llegadaInstalacion', '-')
    presencial_inicio = inc.get('presencial', {}).get('trabajoInicio', '-')
    presencial_fim = inc.get('presencial', {}).get('trabajoFin', '-')
    presencial_duracao = inc.get('presencial', {}).get('duracion', '-')
    presencial_saida = inc.get('presencial', {}).get('salidaInstalacion', '-')
    presencial_resultado = inc.get('presencial', {}).get('resultado', '-')
    
    tipo_texto = {
        'criacao': '🆕 NOVO INCIDENTE',
        'actualizacao': '📝 ATUALIZAÇÃO DE INCIDENTE',
        'cierre': '✅ FECHAMENTO DE INCIDENTE'
    }.get(tipo, '🆕 NOVO INCIDENTE')
    
    resultado_texto = {
        'Resuelta': '✅ RESOLVIDO DEFINITIVAMENTE',
        'Provisional': '⚠️ SOLUÇÃO PROVISÓRIA APLICADA',
        'NoResuelta': '⏳ NÃO RESOLVIDO - PROLONGADO'
    }.get(presencial_resultado, presencial_resultado)
    
    # Acessos
    acessos_html = ""
    if inc.get('acessos') and len(inc['acessos']) > 0:
        for idx, acc in enumerate(inc['acessos']):
            acessos_html += f"""
    ┌──────────────────────────────────────────────────────────────┐
    │ 🔐 ACESSO #{idx+1}
    ├──────────────────────────────────────────────────────────────┤
    │ 📅 Data:           {acc.get('fecha', '-')}
    │ 🕐 Hora entrada:   {acc.get('horaEntrada', '-')} UTC
    │ 🕐 Hora saída:     {acc.get('horaSalida', '-')} UTC
    │ ⏱️ Duração:        {acc.get('duracao', '-')}
    │ 📝 Trabalho:       {acc.get('descricao', '-')}
    └──────────────────────────────────────────────────────────────┘
"""
    else:
        acessos_html = "    └── Nenhum acesso registrado"
    
    # Viagens
    viagens_html = ""
    if inc.get('viajes') and len(inc['viajes']) > 0:
        for idx, via in enumerate(inc['viajes']):
            viagens_html += f"""
    ┌──────────────────────────────────────────────────────────────┐
    │ ✈️ VIAGEM #{idx+1}
    ├──────────────────────────────────────────────────────────────┤
    │ 📅 Data ida:       {via.get('fechaIda', '-')}
    │ 📅 Data volta:     {via.get('fechaVuelta', '-')}
    │ 🚗 Meio:           {via.get('medio', '-')}
    │ 📝 Observações:    {via.get('obs', '-')}
    └──────────────────────────────────────────────────────────────┘
"""
    else:
        viagens_html = "    └── Nenhuma viagem registrada"
    
    corpo = f"""
┌════════════════════════════════════════════════════════════════┐
│                      {tipo_texto}                              │
└════════════════════════════════════════════════════════════════┘

┌────────────────────────────────────────────────────────────────┐
│ 📋 INFORMAÇÕES GERAIS                                          │
├────────────────────────────────────────────────────────────────┤
│ 🆔 ID:                    #{inc_id}
│ 📊 Estado:                {estado}
│ 📅 Data do relatório:     {data}
│ 👤 Operador LACV:         {operador}
│ 📅 Data detecção:         {data_deteccao}
│ 📍 Estação:               {estacao}
│ 🎯 Classificação:         {classificacao}
│ ⚠️ Sintomas:              {sintomas}
│ 📝 Descrição:             {descricao}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 📞 CONTATO INCO                                                │
├────────────────────────────────────────────────────────────────┤
│ 👨‍🔧 Técnico:              {tecnico}
│ 🕐 Hora do contato:       {hora_contato}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 🖥️ INTERVENÇÃO REMOTA                                          │
├────────────────────────────────────────────────────────────────┤
│ 🕐 Início:               {remoto_inicio}
│ 🕐 Fim:                  {remoto_fim}
│ ⏱️ Duração:              {remoto_duracao}
│ ✅ Resolvido?:           {remoto_resolvido}
│ 📝 Observações:          {remoto_obs}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 🔐 ACESSOS REALIZADOS                                          │
├────────────────────────────────────────────────────────────────┤
{acessos_html}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ ✈️ VIAGENS REALIZADAS                                          │
├────────────────────────────────────────────────────────────────┤
{viagens_html}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 🔧 INTERVENÇÃO PRESENCIAL                                      │
├────────────────────────────────────────────────────────────────┤
│ 🏁 Chegada à instalação:   {presencial_chegada}
│ 🔧 Início do trabalho:     {presencial_inicio}
│ ✅ Fim do trabalho:        {presencial_fim}
│ ⏱️ Duração do trabalho:    {presencial_duracao}
│ 🚪 Saída da instalação:    {presencial_saida}
│ 📌 Resultado:              {resultado_texto}
└────────────────────────────────────────────────────────────────┘
"""
    
    if presencial_resultado == 'Provisional':
        corpo += f"""
┌────────────────────────────────────────────────────────────────┐
│ 🩹 SOLUÇÃO PROVISÓRIA                                          │
├────────────────────────────────────────────────────────────────┤
│ 📝 Descrição:         {inc.get('solucionProvincial', {}).get('descricao', '-')}
│ 📊 Cobertura:         {inc.get('solucionProvincial', {}).get('cobertura', '-')}
│ 📅 Data solução def.: {inc.get('solucionProvincial', {}).get('fechaDefinitiva', '-')}
└────────────────────────────────────────────────────────────────┘
"""
    
    if presencial_resultado == 'NoResuelta':
        corpo += f"""
┌────────────────────────────────────────────────────────────────┐
│ ⏳ INCIDENTE PROLONGADO                                         │
├────────────────────────────────────────────────────────────────┤
│ 📝 Motivo:            {inc.get('prolongada', {}).get('motivo', '-')}
│ 📋 Plano seguimento:  {inc.get('prolongada', {}).get('plan', '-')}
│ 🔄 Frequência:        {inc.get('prolongada', {}).get('frecuencia', '-')}
└────────────────────────────────────────────────────────────────┘
"""
    
    corpo += """
┌════════════════════════════════════════════════════════════════┐
│                                                                │
│   📧 Mensagem automática do sistema de gestão de incidentes   │
│   🌐 Acesse a aplicação para mais detalhes e acompanhamento   │
│                                                                │
└════════════════════════════════════════════════════════════════┘
"""
    return corpo

def gerar_correo_solicitacao(tipo, dados):
    data = datetime.now().strftime('%d/%m/%Y %H:%M:%S UTC')
    inc_id = dados.get('incidencia_id', 'N/A')
    estacion = dados.get('estacion', '-')
    operador = dados.get('operador', '-')
    
    # Determinar si es creación o actualización
    is_atualizacao = tipo in ['atualizacao_acesso', 'atualizacao_viagem']
    tipo_texto = "ATUALIZAÇÃO DE " if is_atualizacao else ""
    
    if tipo in ['acesso', 'atualizacao_acesso']:
        asunto = f"🔐 {tipo_texto}SOLICITAÇÃO DE ACESSO - #{inc_id} - {estacion}"
        corpo = f"""
┌════════════════════════════════════════════════════════════════┐
│           {tipo_texto}🔐 SOLICITAÇÃO DE ACESSO À ESTAÇÃO REMOTA          │
└════════════════════════════════════════════════════════════════┘

┌────────────────────────────────────────────────────────────────┐
│ 📋 INFORMAÇÕES GERAIS                                          │
├────────────────────────────────────────────────────────────────┤
│ 🆔 ID do Incidente:    #{inc_id}
│ 📅 Data da solicitação: {data}
│ 📍 Estação:            {estacion}
│ 👤 Operador LACV:      {operador}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 🔐 DETALHES DO ACESSO                                          │
├────────────────────────────────────────────────────────────────┤
│ 👥 Técnico(s):         {dados.get('tecnicos', '-')}
│ 📅 Data da solicitação: {dados.get('solicitacao', '-')}
│ ⏰ Hora estimada:       {dados.get('horaEstimada', '-')} UTC
│ ✅ Data da concessão:   {dados.get('concessao', '-')}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 📎 DOCUMENTOS ANEXADOS                                         │
├────────────────────────────────────────────────────────────────┤
│ {chr(10).join(f'   • {doc}' for doc in dados.get('documentos', [])) if dados.get('documentos') else '   Nenhum documento anexado'}
└────────────────────────────────────────────────────────────────┘

┌════════════════════════════════════════════════════════════════┐
│         Por favor, gerenciar as permissões de acesso           │
└════════════════════════════════════════════════════════════════┘
"""
    else:
        asunto = f"✈️ {tipo_texto}SOLICITAÇÃO DE VIAGEM - #{inc_id} - {estacion}"
        corpo = f"""
┌════════════════════════════════════════════════════════════════┐
│          {tipo_texto}✈️ SOLICITAÇÃO DE VIAGEM À ESTAÇÃO REMOTA             │
└════════════════════════════════════════════════════════════════┘

┌────────────────────────────────────────────────────────────────┐
│ 📋 INFORMAÇÕES GERAIS                                          │
├────────────────────────────────────────────────────────────────┤
│ 🆔 ID do Incidente:    #{inc_id}
│ 📅 Data da solicitação: {data}
│ 📍 Estação:            {estacion}
│ 👤 Operador LACV:      {operador}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ ✈️ DETALHES DA VIAGEM                                          │
├────────────────────────────────────────────────────────────────┤
│ 👥 Técnico(s):         {dados.get('tecnicos', '-')}
│ 📅 Data da solicitação: {dados.get('solicitacao', '-')}
│ ✅ Data da confirmação: {dados.get('confirmacao', '-')}
│ 📅 Data ida:           {dados.get('fecha_ida', '-')}
│ 📅 Data volta:         {dados.get('fecha_vuelta', '-')}
│ 🚗 Meio transporte:    {dados.get('medio', '-')}
│ 🧳 Maletas:            {dados.get('maletas', '0')}
│ 🏨 Dias de hotel:      {dados.get('hotelDias', '0')}
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 📝 OBSERVAÇÕES                                                 │
├────────────────────────────────────────────────────────────────┤
│ {dados.get('obs', '-')}
└────────────────────────────────────────────────────────────────┘

┌════════════════════════════════════════════════════════════════┐
│        Por favor, gerenciar o deslocamento e a logística       │
└════════════════════════════════════════════════════════════════┘
"""
    return asunto, corpo

# ============================================================
# FUNCIONES DE DADOS
# ============================================================

def ler_incidencias():
    """Lee incidencias con manejo de errores"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error al leer incidencias JSON: {e}")
    except IOError as e:
        print(f"❌ Error al abrir archivo de incidencias: {e}")
    return []

def guardar_incidencias(incidencias):
    """Guarda incidencias con manejo de errores y validación de estructura"""
    try:
        # IMPORTANTE: Validar y normalizar la estructura
        for inc in incidencias:
            # Asegurar que remoto existe y es un diccionario
            if 'remoto' not in inc or not isinstance(inc.get('remoto'), dict):
                inc['remoto'] = {}
            
            # Asegurar que presencial existe y es un diccionario
            if 'presencial' not in inc or not isinstance(inc.get('presencial'), dict):
                inc['presencial'] = {}
            
            # Asegurar que acessos existe y es una lista
            if 'acessos' not in inc or not isinstance(inc.get('acessos'), list):
                inc['acessos'] = []
            
            # Asegurar que viagens existe y es una lista
            if 'viajes' not in inc or not isinstance(inc.get('viajes'), list):
                inc['viajes'] = []
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(incidencias, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"❌ Error al guardar incidencias: {e}")
        return False

# ============================================================
# PÁGINAS HTML
# ============================================================

@app.route('/')
@login_required
def dashboard():
    return send_from_directory('static', 'dashboard.html')

@app.route('/login')
def login_page():
    return send_from_directory('static', 'index.html')

@app.route('/incidencias/ativas')
@login_required
def incidencias_ativas():
    return send_from_directory('static', 'incidencias_ativas.html')

@app.route('/incidencias/fechadas')
@login_required
def incidencias_fechadas():
    return send_from_directory('static', 'incidencias_cerradas.html')

@app.route('/incidencia/nova')
@login_required
def nova_incidencia():
    return send_from_directory('static', 'nova_incidencia.html')

@app.route('/incidencia/editar/<int:id>')
@role_required('admin', 'tecnico')
def editar_incidencia(id):
    return send_from_directory('static', 'editar_incidencia.html')

@app.route('/configuracoes')
@role_required('admin')
def configuracoes():
    return send_from_directory('static', 'configuracoes.html')

@app.route('/relatorios')
@login_required
def relatorios():
    return send_from_directory('static', 'relatorios.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Usuario o contraseña vacías'}), 400
    
    config = ler_config()
    users = config.get('users', {})
    
    if username in users and check_password_hash(users[username].get('password', ''), password):
        session['username'] = username
        session['role'] = users[username].get('role')
        return jsonify({'success': True, 'username': username, 'role': session['role']})
    return jsonify({'success': False, 'error': 'Usuario o contraseña inválidos'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'username' in session:
        config = ler_config()
        user = config['users'].get(session['username'], {})
        return jsonify({'authenticated': True, 'username': session['username'], 'role': user.get('role', '')})
    return jsonify({'authenticated': False})

@app.route('/api/user-role', methods=['GET'])
@login_required
def get_user_role_api():
    config = ler_config()
    user = config['users'].get(session['username'], {})
    return jsonify({'username': session['username'], 'role': user.get('role', 'operador'), 'name': user.get('name', session['username'])})

@app.route('/api/incidencias', methods=['GET'])
def get_incidencias():
    return jsonify(ler_incidencias())

@app.route('/api/incidencias', methods=['POST'])
def post_incidencias():
    try:
        incidencias = request.json
        if not isinstance(incidencias, list):
            return jsonify({'success': False, 'error': 'Formato de datos inválido'}), 400
        
        if guardar_incidencias(incidencias):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar las incidencias'}), 500
    except (ValueError, TypeError) as e:
        print(f"Error en formato de datos: {e}")
        return jsonify({'success': False, 'error': 'Formato de datos inválido'}), 400
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enviar-correo', methods=['POST'])
def api_enviar_correo():
    try:
        data = request.json
        incidencia = data.get('incidencia', {})
        tipo = data.get('tipo', 'criacao')
        
        tipo_email = {
            'criacao': 'novo_incidente',
            'actualizacao': 'atualizacao',
            'cierre': 'fechamento'
        }.get(tipo, 'novo_incidente')
        
        # CORREGIDO: Usar consistentemente 'classificacao'
        clas_valor = incidencia.get('classificacao', '')
        if clas_valor in ['Crítica', 'Alta', 'ALTA']:
            classificacao = 'ALTA'
        else:
            classificacao = 'BAIXA'
        
        asunto = f"[VHF] {tipo.upper()} - #{incidencia.get('id')} - {incidencia.get('estacion', '')} - {classificacao}"
        corpo_texto = gerar_correo_incidencia(incidencia, tipo)
        
        logo_path = os.path.join('static', 'logo.png')
        thread = threading.Thread(target=enviar_correo, args=(tipo_email, asunto, corpo_texto, logo_path if os.path.exists(logo_path) else None))
        thread.daemon = True
        thread.start()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enviar-solicitud', methods=['POST'])
def api_enviar_solicitud():
    try:
        data = request.json
        tipo_solicitacao = data.get('tipo', 'acesso')
        dados = data.get('dados', {})
        
        # Mapear tipo para configuración de email
        if tipo_solicitacao in ['acesso', 'atualizacao_acesso']:
            tipo_email = 'solicitacao_acesso'
        else:
            tipo_email = 'solicitacao_viagem'
        
        asunto, corpo_texto = gerar_correo_solicitacao(tipo_solicitacao, dados)
        
        thread = threading.Thread(target=enviar_correo, args=(tipo_email, asunto, corpo_texto, None))
        thread.daemon = True
        thread.start()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# ENDPOINTS DE CONFIGURACIÓN
# ============================================================

@app.route('/api/config', methods=['GET'])
@role_required('admin')
def get_config():
    config = ler_config()
    config_safe = {
        'users': {u: {'role': info['role'], 'name': info.get('name', u)} for u, info in config.get('users', {}).items()},
        'emails': config.get('emails', {}),
        'stations': config.get('stations', []),
        'timezone': config.get('timezone', {'offset': 0, 'daylight_saving': 'auto', 'time_format': '24h'}),
        'smtp': {k: v for k, v in config.get('smtp', {}).items() if k != 'password'}
    }
    return jsonify(config_safe)

@app.route('/api/config/users', methods=['POST'])
@role_required('admin')
def add_user():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', '').strip()
        name = data.get('name', username).strip()
        
        if not username or not password or not role:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        if len(password) < 8:
            return jsonify({'success': False, 'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
        
        config = ler_config()
        if username in config.get('users', {}):
            return jsonify({'success': False, 'error': 'El usuario ya existe'}), 400
        
        if 'users' not in config:
            config['users'] = {}
        
        config['users'][username] = {
            'password': generate_password_hash(password),
            'role': role,
            'name': name
        }
        
        if guardar_config(config):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/users/<username>', methods=['DELETE'])
@role_required('admin')
def delete_user(username):
    try:
        if username == 'admin':
            return jsonify({'success': False, 'error': 'No es posible remover el usuario admin'}), 400
        
        config = ler_config()
        if username not in config.get('users', {}):
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        
        del config['users'][username]
        if guardar_config(config):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/emails', methods=['POST'])
@role_required('admin')
def update_emails():
    try:
        data = request.json
        tipo = data.get('tipo', '').strip()
        emails = data.get('emails', [])
        
        if not tipo:
            return jsonify({'success': False, 'error': 'Tipo no especificado'}), 400
        
        if not validate_emails(emails):
            return jsonify({'success': False, 'error': 'Uno o más emails son inválidos'}), 400
        
        config = ler_config()
        if 'emails' not in config:
            config['emails'] = {}
        
        config['emails'][tipo] = emails
        if guardar_config(config):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/stations', methods=['GET'])
@login_required
def get_stations():
    config = ler_config()
    stations = config.get('stations', [])
    return jsonify(stations)

@app.route('/api/config/stations', methods=['POST'])
@role_required('admin')
def add_station():
    try:
        data = request.json
        station_name = data.get('name', '').strip()
        station_type = data.get('type', 'remota').strip()
        
        if not station_name:
            return jsonify({'success': False, 'error': 'Nombre de estación requerido'}), 400
        
        config = ler_config()
        if 'stations' not in config:
            config['stations'] = []
        
        new_id = max([s.get('id', 0) for s in config['stations']] + [0]) + 1
        new_station = {
            'id': new_id,
            'name': station_name,
            'type': station_type,
            'active': True
        }
        config['stations'].append(new_station)
        if guardar_config(config):
            return jsonify({'success': True, 'station': new_station})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/stations/<int:id>', methods=['PUT'])
@role_required('admin')
def update_station(id):
    try:
        data = request.json
        config = ler_config()
        stations = config.get('stations', [])
        for i, s in enumerate(stations):
            if s.get('id') == id:
                stations[i]['name'] = data.get('name', s['name']).strip()
                stations[i]['type'] = data.get('type', s['type']).strip()
                stations[i]['active'] = data.get('active', s['active'])
                if guardar_config(config):
                    return jsonify({'success': True})
                return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
        return jsonify({'success': False, 'error': 'Estación no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/stations/<int:id>', methods=['DELETE'])
@role_required('admin')
def delete_station(id):
    try:
        config = ler_config()
        stations = config.get('stations', [])
        incidencias = ler_incidencias()
        station_name = next((s['name'] for s in stations if s.get('id') == id), None)
        if station_name:
            for inc in incidencias:
                if inc.get('estacion') == station_name:
                    return jsonify({'success': False, 'error': 'La estación tiene incidentes asociados'}), 400
        config['stations'] = [s for s in stations if s.get('id') != id]
        if guardar_config(config):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/smtp', methods=['POST'])
@role_required('admin')
def save_smtp_config():
    try:
        data = request.json
        config = ler_config()
        
        # Validar email
        if not is_valid_email(data.get('username', '')):
            return jsonify({'success': False, 'error': 'Email de usuario SMTP inválido'}), 400
        
        config['smtp'] = {
            'server': data.get('server', '').strip(),
            'port': int(data.get('port', 587)),
            'security': data.get('security', 'TLS'),
            'username': data.get('username', '').strip(),
            'from_name': data.get('from_name', '').strip()
        }
        
        if guardar_config(config):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except ValueError as e:
        return jsonify({'success': False, 'error': 'Datos inválidos'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/smtp', methods=['GET'])
@role_required('admin')
def get_smtp_config():
    config = ler_config()
    smtp = config.get('smtp', {})
    smtp_safe = {
        'server': smtp.get('server', 'smtp.serviciodecorreo.es'),
        'port': smtp.get('port', 587),
        'security': smtp.get('security', 'TLS'),
        'username': smtp.get('username', ''),
        'from_name': smtp.get('from_name', 'Sistema de Gestão de Incidentes VHF')
    }
    return jsonify(smtp_safe)

@app.route('/api/config/test-email', methods=['POST'])
@role_required('admin')
def test_email_config():
    try:
        data = request.json
        smtp_config = data.get('config', {})
        destinatario = data.get('destinatario', '').strip()
        
        if not destinatario or not is_valid_email(destinatario):
            return jsonify({'success': False, 'error': 'Email destinatario inválido'}), 400
        
        msg = MIMEMultipart()
        msg['Subject'] = "Teste de Configuração SMTP - Sistema VHF"
        msg['From'] = f"{smtp_config.get('from_name', 'Sistema VHF')} <{smtp_config.get('username')}>"
        msg['To'] = destinatario
        msg.attach(MIMEText("Este é um email de teste do Sistema de Gestão de Incidentes VHF. A configuração SMTP está funcionando corretamente!", 'plain', 'utf-8'))
        
        if smtp_config.get('security') == 'SSL':
            server = smtplib.SMTP_SSL(smtp_config.get('server'), smtp_config.get('port'), timeout=30)
        else:
            server = smtplib.SMTP(smtp_config.get('server'), smtp_config.get('port'), timeout=30)
            server.starttls()
        
        server.login(smtp_config.get('username'), smtp_config.get('password'))
        server.sendmail(smtp_config.get('username'), [destinatario], msg.as_string())
        server.quit()
        return jsonify({'success': True})
    except smtplib.SMTPException as e:
        return jsonify({'success': False, 'error': f'Error SMTP: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# CONFIGURACIÓN DE FUSO HORARIO
# ============================================================

@app.route('/api/config/timezone', methods=['GET'])
@login_required
def get_timezone_config():
    config = ler_config()
    timezone = config.get('timezone', {'offset': 0, 'daylight_saving': 'auto', 'time_format': '24h'})
    return jsonify(timezone)

@app.route('/api/config/timezone', methods=['POST'])
@role_required('admin')
def save_timezone_config():
    try:
        data = request.json
        config = ler_config()
        config['timezone'] = {
            'offset': int(data.get('offset', 0)),
            'daylight_saving': data.get('daylight_saving', 'auto'),
            'time_format': data.get('time_format', '24h')
        }
        if guardar_config(config):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No se pudo guardar la configuración'}), 500
    except ValueError:
        return jsonify({'success': False, 'error': 'Datos inválidos'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# INICIAR SERVIDOR
# ============================================================

def mostrar_info_red():
    print("\n" + "="*60)
    print("📡 SERVIDOR DE INCIDENTES VHF INICIADO")
    print("="*60)
    print(f"\n📍 Aceso LOCAL: http://localhost:{PORT}")
    try:
        hostname = socket.gethostname()
        ip_local = socket.gethostbyname(hostname)
        print(f"📍 Aceso REDE: http://{ip_local}:{PORT}")
    except:
        pass
    print(f"\n📁 Datos: {os.path.abspath(DATA_FILE)}")
    print(f"⚙️ Configuración: {os.path.abspath(CONFIG_FILE)}")
    config = ler_config()
    print(f"\n👤 Usuarios configurados:")
    for user, info in config.get('users', {}).items():
        print(f"   - {user} ({info.get('role', '?')})")
    print(f"\n📡 Estaciones configuradas:")
    for station in config.get('stations', []):
        print(f"   - {station['name']} ({station['type']})")
    print("\n✅ Servidor listo. Ctrl+C para parar.")
    print("="*60 + "\n")

if __name__ == '__main__':
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    mostrar_info_red()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
