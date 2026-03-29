<<<<<<< HEAD
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import re
from config import EMAIL_FROM_NAME, GMAIL_ADDRESS, GMAIL_APP_PASSWORD


# We use .get() so it doesn't crash on startup if not set yet
GMAIL_ADDRESS      = GMAIL_ADDRESS
GMAIL_APP_PASSWORD = GMAIL_APP_PASSWORD
EMAIL_FROM_NAME    = EMAIL_FROM_NAME

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587    # use TLS port 587, NOT SSL port 465

def _send_email_sync(to: str, subject: str, html_body: str):
    """
    Synchronous SMTP send — runs in a thread via asyncio.
    Uses STARTTLS (port 587) for secure connection.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("ERROR: Gmail credentials missing. Cannot send email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((EMAIL_FROM_NAME, GMAIL_ADDRESS))
    msg["To"]      = to

    # Plain text fallback (strip HTML tags simply)
    plain_text = html_body.replace("<br>", "\n").replace("</p>", "\n")
    plain_text = re.sub(r"<[^>]+>", "", plain_text)

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()          # upgrades to encrypted connection
        server.ehlo()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(
            from_addr=GMAIL_ADDRESS,
            to_addrs=[to],
            msg=msg.as_string()
        )

async def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Async wrapper — runs the blocking SMTP call in a thread pool
    so it does not block the FastAPI event loop.
    Silently logs errors — never crashes the caller.
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _send_email_sync,
            to,
            subject,
            html_body
        )
        print(f"Email sent to {to}: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed. Check GMAIL_APP_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        print(f"ERROR: SMTP error sending to {to}: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Failed to send email to {to}: {e}")
        return False


def skin_email_html(data: dict) -> str:
    action_color = {
        "self-care": "#22c55e",
        "clinic":    "#f59e0b",
        "emergency": "#ef4444"
    }.get(data.get("recommended_action", "clinic"), "#f59e0b")

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <div style="background:#0ea5e9;padding:20px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:22px">
          DermaAssess — Skin Assessment Result
        </h1>
      </div>
      <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px;
                    border-left:4px solid {action_color}">
          <p style="margin:0;font-size:16px;font-weight:bold;color:{action_color}">
            Recommended action: {data.get("recommended_action","—").upper()}
          </p>
          <p style="margin:8px 0 0;color:#475569">{data.get("ai_diagnosis","")}</p>
        </div>
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
          <tr>
            <td style="padding:8px;background:white;border-radius:8px;text-align:center;width:50%">
              <div style="font-size:28px;font-weight:bold;color:#0f172a">
                {data.get("severity_score","—")}/10
              </div>
              <div style="color:#64748b;font-size:12px">Severity score</div>
            </td>
            <td style="width:8px"></td>
            <td style="padding:8px;background:white;border-radius:8px;text-align:center">
              <div style="font-size:18px;font-weight:bold;color:#0f172a;text-transform:capitalize">
                {data.get("contagion_risk","—")}
              </div>
              <div style="color:#64748b;font-size:12px">Contagion risk</div>
            </td>
          </tr>
        </table>
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px">
          <h3 style="margin:0 0 8px;color:#0f172a">AI Advice</h3>
          <p style="margin:0;color:#475569;line-height:1.6">
            {data.get("ai_advice","")}
          </p>
        </div>
        <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0">
          This is AI guidance only — not a medical diagnosis.<br>
          Always consult a qualified healthcare professional.
        </p>
      </div>
    </body></html>
    """


def prescription_email_html(data: dict) -> str:
    safety_color = {
        "safe":      "#22c55e",
        "caution":   "#f59e0b",
        "dangerous": "#ef4444"
    }.get(data.get("overall_safety","caution"), "#f59e0b")

    alerts_html = ""
    if data.get("allergy_alerts"):
        items = "".join(f"<li style='color:#ef4444'>{a}</li>"
                        for a in data["allergy_alerts"])
        alerts_html = f"""
        <div style="background:#fef2f2;border-radius:8px;padding:16px;margin-bottom:12px">
          <h3 style="margin:0 0 8px;color:#ef4444">Allergy Alerts</h3>
          <ul style="margin:0;padding-left:20px">{items}</ul>
        </div>"""

    interactions_html = ""
    if data.get("interactions"):
        items = "".join(f"<li style='color:#92400e'>{i}</li>"
                        for i in data["interactions"])
        interactions_html = f"""
        <div style="background:#fffbeb;border-radius:8px;padding:16px;margin-bottom:12px">
          <h3 style="margin:0 0 8px;color:#d97706">Drug Interactions</h3>
          <ul style="margin:0;padding-left:20px">{items}</ul>
        </div>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <div style="background:#7c3aed;padding:20px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:22px">
          MediSafe — Prescription Scan Result
        </h1>
      </div>
      <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px;
                    border-left:4px solid {safety_color}">
          <p style="margin:0;font-weight:bold;color:{safety_color};font-size:16px;text-transform:uppercase">
            Safety: {data.get("overall_safety","—")}
          </p>
          <p style="margin:8px 0 0;color:#475569">{data.get("safety_advice","")}</p>
        </div>
        <p style="color:#475569">
          <strong>{data.get("medicines_count",0)} medicines</strong> found in prescription.
        </p>
        {alerts_html}
        {interactions_html}
        <p style="color:#94a3b8;font-size:12px;text-align:center;margin:16px 0 0">
          Always verify with your pharmacist before taking any medication.
        </p>
      </div>
    </body></html>
    """

def weight_email_html(data: dict) -> str:
    meal_html = ""
    if data.get("meal_description"):
        meal_html = f"""
        <tr>
          <td style="padding:8px 0;color:#64748b">Meal</td>
          <td style="padding:8px 0;color:#0f172a;font-weight:bold">
            {data["meal_description"]}
          </td>
        </tr>"""

    calories_html = ""
    if data.get("calories"):
        calories_html = f"""
        <tr>
          <td style="padding:8px 0;color:#64748b">Est. calories</td>
          <td style="padding:8px 0;color:#0f172a;font-weight:bold">
            {data["calories"]} kcal
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <div style="background:#f59e0b;padding:20px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:22px">
          Weight AI — Log Confirmed
        </h1>
      </div>
      <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px">
          <table style="width:100%">
            <tr>
              <td style="padding:8px 0;color:#64748b">Weight logged</td>
              <td style="padding:8px 0;color:#0f172a;font-weight:bold;font-size:20px">
                {data.get("weight_kg","—")} kg
              </td>
            </tr>
            {meal_html}
            {calories_html}
          </table>
        </div>
        <div style="background:#f0fdf4;border-radius:8px;padding:16px">
          <p style="margin:0;color:#166534">
            💡 {data.get("ai_advice","Keep up the great work!")}
          </p>
        </div>
      </div>
    </body></html>
    """
=======
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import re
from config import EMAIL_FROM_NAME, GMAIL_ADDRESS, GMAIL_APP_PASSWORD


# We use .get() so it doesn't crash on startup if not set yet
GMAIL_ADDRESS      = GMAIL_ADDRESS
GMAIL_APP_PASSWORD = GMAIL_APP_PASSWORD
EMAIL_FROM_NAME    = EMAIL_FROM_NAME

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587    # use TLS port 587, NOT SSL port 465

def _send_email_sync(to: str, subject: str, html_body: str):
    """
    Synchronous SMTP send — runs in a thread via asyncio.
    Uses STARTTLS (port 587) for secure connection.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("ERROR: Gmail credentials missing. Cannot send email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((EMAIL_FROM_NAME, GMAIL_ADDRESS))
    msg["To"]      = to

    # Plain text fallback (strip HTML tags simply)
    plain_text = html_body.replace("<br>", "\n").replace("</p>", "\n")
    plain_text = re.sub(r"<[^>]+>", "", plain_text)

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()          # upgrades to encrypted connection
        server.ehlo()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(
            from_addr=GMAIL_ADDRESS,
            to_addrs=[to],
            msg=msg.as_string()
        )

async def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Async wrapper — runs the blocking SMTP call in a thread pool
    so it does not block the FastAPI event loop.
    Silently logs errors — never crashes the caller.
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _send_email_sync,
            to,
            subject,
            html_body
        )
        print(f"Email sent to {to}: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed. Check GMAIL_APP_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        print(f"ERROR: SMTP error sending to {to}: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Failed to send email to {to}: {e}")
        return False


def skin_email_html(data: dict) -> str:
    action_color = {
        "self-care": "#22c55e",
        "clinic":    "#f59e0b",
        "emergency": "#ef4444"
    }.get(data.get("recommended_action", "clinic"), "#f59e0b")

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <div style="background:#0ea5e9;padding:20px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:22px">
          DermaAssess — Skin Assessment Result
        </h1>
      </div>
      <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px;
                    border-left:4px solid {action_color}">
          <p style="margin:0;font-size:16px;font-weight:bold;color:{action_color}">
            Recommended action: {data.get("recommended_action","—").upper()}
          </p>
          <p style="margin:8px 0 0;color:#475569">{data.get("ai_diagnosis","")}</p>
        </div>
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
          <tr>
            <td style="padding:8px;background:white;border-radius:8px;text-align:center;width:50%">
              <div style="font-size:28px;font-weight:bold;color:#0f172a">
                {data.get("severity_score","—")}/10
              </div>
              <div style="color:#64748b;font-size:12px">Severity score</div>
            </td>
            <td style="width:8px"></td>
            <td style="padding:8px;background:white;border-radius:8px;text-align:center">
              <div style="font-size:18px;font-weight:bold;color:#0f172a;text-transform:capitalize">
                {data.get("contagion_risk","—")}
              </div>
              <div style="color:#64748b;font-size:12px">Contagion risk</div>
            </td>
          </tr>
        </table>
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px">
          <h3 style="margin:0 0 8px;color:#0f172a">AI Advice</h3>
          <p style="margin:0;color:#475569;line-height:1.6">
            {data.get("ai_advice","")}
          </p>
        </div>
        <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0">
          This is AI guidance only — not a medical diagnosis.<br>
          Always consult a qualified healthcare professional.
        </p>
      </div>
    </body></html>
    """


def prescription_email_html(data: dict) -> str:
    safety_color = {
        "safe":      "#22c55e",
        "caution":   "#f59e0b",
        "dangerous": "#ef4444"
    }.get(data.get("overall_safety","caution"), "#f59e0b")

    alerts_html = ""
    if data.get("allergy_alerts"):
        items = "".join(f"<li style='color:#ef4444'>{a}</li>"
                        for a in data["allergy_alerts"])
        alerts_html = f"""
        <div style="background:#fef2f2;border-radius:8px;padding:16px;margin-bottom:12px">
          <h3 style="margin:0 0 8px;color:#ef4444">Allergy Alerts</h3>
          <ul style="margin:0;padding-left:20px">{items}</ul>
        </div>"""

    interactions_html = ""
    if data.get("interactions"):
        items = "".join(f"<li style='color:#92400e'>{i}</li>"
                        for i in data["interactions"])
        interactions_html = f"""
        <div style="background:#fffbeb;border-radius:8px;padding:16px;margin-bottom:12px">
          <h3 style="margin:0 0 8px;color:#d97706">Drug Interactions</h3>
          <ul style="margin:0;padding-left:20px">{items}</ul>
        </div>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <div style="background:#7c3aed;padding:20px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:22px">
          MediSafe — Prescription Scan Result
        </h1>
      </div>
      <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px;
                    border-left:4px solid {safety_color}">
          <p style="margin:0;font-weight:bold;color:{safety_color};font-size:16px;text-transform:uppercase">
            Safety: {data.get("overall_safety","—")}
          </p>
          <p style="margin:8px 0 0;color:#475569">{data.get("safety_advice","")}</p>
        </div>
        <p style="color:#475569">
          <strong>{data.get("medicines_count",0)} medicines</strong> found in prescription.
        </p>
        {alerts_html}
        {interactions_html}
        <p style="color:#94a3b8;font-size:12px;text-align:center;margin:16px 0 0">
          Always verify with your pharmacist before taking any medication.
        </p>
      </div>
    </body></html>
    """

def weight_email_html(data: dict) -> str:
    meal_html = ""
    if data.get("meal_description"):
        meal_html = f"""
        <tr>
          <td style="padding:8px 0;color:#64748b">Meal</td>
          <td style="padding:8px 0;color:#0f172a;font-weight:bold">
            {data["meal_description"]}
          </td>
        </tr>"""

    calories_html = ""
    if data.get("calories"):
        calories_html = f"""
        <tr>
          <td style="padding:8px 0;color:#64748b">Est. calories</td>
          <td style="padding:8px 0;color:#0f172a;font-weight:bold">
            {data["calories"]} kcal
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <div style="background:#f59e0b;padding:20px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:22px">
          Weight AI — Log Confirmed
        </h1>
      </div>
      <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px">
          <table style="width:100%">
            <tr>
              <td style="padding:8px 0;color:#64748b">Weight logged</td>
              <td style="padding:8px 0;color:#0f172a;font-weight:bold;font-size:20px">
                {data.get("weight_kg","—")} kg
              </td>
            </tr>
            {meal_html}
            {calories_html}
          </table>
        </div>
        <div style="background:#f0fdf4;border-radius:8px;padding:16px">
          <p style="margin:0;color:#166534">
            💡 {data.get("ai_advice","Keep up the great work!")}
          </p>
        </div>
      </div>
    </body></html>
    """
>>>>>>> 3efa2a2850a1b0535bb86f92f3a35fd5c8ece0cc
