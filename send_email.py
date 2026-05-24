# send_email.py - Script independiente para enviar correos
import sys
import json
import smtplib
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: No file provided")
        sys.exit(1)
    
    temp_file = sys.argv[1]
    
    try:
        with open(temp_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        os.remove(temp_file)
    except Exception as e:
        print(f"ERROR reading file: {e}")
        sys.exit(1)
    
    SMTP_SERVER = "smtp.serviciodecorreo.es"
    SMTP_PORT = 587
    SMTP_USER = "incidencias.lacv@incoengenheiros.com"
    SMTP_PASSWORD = "Inco2026l@cv"
    FROM_EMAIL = "incidencias.lacv@incoengenheiros.com"
    FROM_NAME = "Sistema Incidencias VHF"
    
    destinatarios = data.get('destinatarios', [])
    asunto = data.get('asunto', '')
    cuerpo = data.get('cuerpo', '')
    
    print(f"Enviando a: {', '.join(destinatarios)}")
    print(f"Longitud mensaje: {len(cuerpo)} caracteres")
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = asunto
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = ', '.join(destinatarios)
        msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=60)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, destinatarios, msg.as_string())
        server.quit()
        
        print("ENVIADO")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)