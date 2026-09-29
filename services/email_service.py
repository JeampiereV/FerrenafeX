import smtplib
from email.message import EmailMessage
from flask import current_app

def send_email(to, subject, html, text=None):
    server=current_app.config.get('MAIL_SERVER')
    username=current_app.config.get('MAIL_USERNAME')
    password=current_app.config.get('MAIL_PASSWORD')
    sender=current_app.config.get('MAIL_DEFAULT_SENDER') or username
    if not server or not sender or not to:
        return False
    msg=EmailMessage()
    msg['Subject']=subject
    msg['From']=sender
    msg['To']=to
    msg.set_content(text or 'FerreñafeX')
    msg.add_alternative(html, subtype='html')
    try:
        port=int(current_app.config.get('MAIL_PORT') or 587)
        if port==465:
            with smtplib.SMTP_SSL(server,port,timeout=12) as smtp:
                if username and password: smtp.login(username,password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server,port,timeout=12) as smtp:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
                if username and password: smtp.login(username,password)
                smtp.send_message(msg)
        return True
    except Exception:
        return False

def send_account_approved(user):
    base=current_app.config.get('APP_BASE_URL') or ''
    link=f'{base}/login' if base else '/login'
    name=f"{user['names']} {user['last_names']}".strip()
    html=f'''<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#171a19">
    <h1 style="margin-bottom:8px">FerreñafeX</h1>
    <p>Hola, <strong>{name}</strong>.</p>
    <p>Tu solicitud de registro ha sido <strong>aprobada</strong>. Ya puedes ingresar a FerreñafeX con tus credenciales.</p>
    <p><a href="{link}" style="display:inline-block;padding:12px 18px;background:#171a19;color:#fff;text-decoration:none;border-radius:8px">Ingresar a FerreñafeX</a></p>
    <p>Gracias por formar parte de la comunidad FerreñafeX.</p></div>'''
    text=f"Hola, {name}. Tu cuenta de FerreñafeX fue aprobada. Ingresa aquí: {link}"
    return send_email(user['email'] if 'email' in user.keys() else None, 'Tu cuenta de FerreñafeX fue aprobada', html, text)

def send_account_rejected(user):
    name=f"{user['names']} {user['last_names']}".strip()
    html=f'''<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#171a19">
    <h1>FerreñafeX</h1><p>Hola, <strong>{name}</strong>.</p>
    <p>Tu solicitud de registro no fue aprobada en esta ocasión.</p>
    <p>Si consideras que se trata de un error, puedes volver a consultar los canales de contacto de FerreñafeX.</p>
    <p>Atentamente,<br>FerreñafeX</p></div>'''
    return send_email(user['email'] if 'email' in user.keys() else None, 'Actualización de tu solicitud de FerreñafeX', html,
                      f"Hola, {name}. Tu solicitud de registro en FerreñafeX no fue aprobada en esta ocasión.")
