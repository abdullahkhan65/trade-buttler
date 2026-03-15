import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT

logger = logging.getLogger(__name__)

def send_email(subject, html_body):
    """Send HTML email via Gmail SMTP."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENT:
        logger.warning("Email not configured, skipping send")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECIPIENT
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        logger.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def send_forming_email(signal):
    subject = f"⚠️ {signal['symbol']} {signal['direction']} Setup Forming — Prepare"
    reasons_html = "".join([f"<li>{r}</li>" for r in signal['reasons']])

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="background:#0d1117;color:#e6edf3;font-family:'Arial',sans-serif;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#1a1200,#2d2000);border:1px solid #c9a84c;border-radius:12px;padding:0;overflow:hidden;">

      <!-- Header -->
      <div style="background:linear-gradient(90deg,#c9a84c,#f5d87e);padding:20px 30px;">
        <h1 style="margin:0;color:#000;font-size:24px;font-weight:bold;">⚠️ SETUP FORMING</h1>
        <p style="margin:5px 0 0;color:#333;font-size:16px;">{signal['symbol']} — {signal['direction']}</p>
      </div>

      <!-- Body -->
      <div style="padding:30px;">
        <div style="display:grid;gap:15px;">
          <div style="background:#1a1a2e;border-radius:8px;padding:15px;border-left:4px solid #c9a84c;">
            <div style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Entry Zone</div>
            <div style="color:#f5d87e;font-size:28px;font-weight:bold;">${signal['entry_price']:,.2f}</div>
          </div>

          <div style="display:flex;gap:15px;">
            <div style="flex:1;background:#1a1a2e;border-radius:8px;padding:15px;border-left:4px solid #ef4444;">
              <div style="color:#888;font-size:12px;text-transform:uppercase;">Stop Loss</div>
              <div style="color:#ef4444;font-size:20px;font-weight:bold;">${signal['stop_loss']:,.2f}</div>
            </div>
            <div style="flex:1;background:#1a1a2e;border-radius:8px;padding:15px;border-left:4px solid #22c55e;">
              <div style="color:#888;font-size:12px;text-transform:uppercase;">Take Profit</div>
              <div style="color:#22c55e;font-size:20px;font-weight:bold;">${signal['take_profit']:,.2f}</div>
            </div>
          </div>

          <div style="background:#1a1a2e;border-radius:8px;padding:15px;">
            <div style="color:#888;font-size:12px;text-transform:uppercase;margin-bottom:10px;">Confluence Factors</div>
            <ul style="margin:0;padding-left:20px;color:#e6edf3;line-height:1.8;">
              {reasons_html}
            </ul>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div style="background:#1a1200;padding:15px 30px;border-top:1px solid #c9a84c33;text-align:center;">
        <div style="color:#c9a84c;font-size:14px;font-weight:bold;">Score: {signal['score']}/9 — Setup developing, not confirmed yet</div>
        <div style="color:#666;font-size:12px;margin-top:5px;">Wait for confirmation before executing. Confidence: {signal['confidence']}%</div>
      </div>
    </div>
    <p style="color:#444;font-size:11px;text-align:center;margin-top:10px;">Trade Buttler Signal Engine</p>
  </div>
</body>
</html>"""
    return send_email(subject, html)

def send_confirmed_email(signal):
    direction = signal['direction']
    color = "#22c55e" if direction == "BUY" else "#ef4444"
    bg_color = "#001a0d" if direction == "BUY" else "#1a0000"
    emoji = "🚀" if direction == "BUY" else "🔻"

    reasons_html = "".join([f"<li>{r}</li>" for r in signal['reasons']])

    rr_ratio = abs(signal['take_profit'] - signal['entry_price']) / abs(signal['stop_loss'] - signal['entry_price']) if abs(signal['stop_loss'] - signal['entry_price']) > 0 else 0

    subject = f"🚨 EXECUTE NOW: {signal['symbol']} {direction} @ ${signal['entry_price']:,.2f}"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="background:#0d1117;color:#e6edf3;font-family:'Arial',sans-serif;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,{bg_color},{bg_color});border:2px solid {color};border-radius:12px;overflow:hidden;">

      <!-- Header -->
      <div style="background:linear-gradient(90deg,{color},{color}99);padding:20px 30px;">
        <h1 style="margin:0;color:#fff;font-size:26px;font-weight:bold;">{emoji} EXECUTE NOW</h1>
        <p style="margin:5px 0 0;color:#ffffffcc;font-size:18px;">{signal['symbol']} — {direction}</p>
      </div>

      <!-- ALERT BANNER -->
      <div style="background:{color}22;border-bottom:1px solid {color}44;padding:12px 30px;text-align:center;">
        <span style="color:{color};font-size:15px;font-weight:bold;">HIGH CONFLUENCE SIGNAL — EXECUTE AT MARKET OR LIMIT</span>
      </div>

      <!-- Body -->
      <div style="padding:30px;">
        <div style="background:#111;border-radius:8px;padding:20px;border:2px solid {color};margin-bottom:20px;">
          <div style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:2px;">ENTRY PRICE</div>
          <div style="color:{color};font-size:36px;font-weight:bold;">${signal['entry_price']:,.2f}</div>
        </div>

        <div style="display:flex;gap:15px;margin-bottom:20px;">
          <div style="flex:1;background:#111;border-radius:8px;padding:15px;border-left:4px solid #ef4444;">
            <div style="color:#888;font-size:11px;text-transform:uppercase;">Stop Loss</div>
            <div style="color:#ef4444;font-size:22px;font-weight:bold;">${signal['stop_loss']:,.2f}</div>
          </div>
          <div style="flex:1;background:#111;border-radius:8px;padding:15px;border-left:4px solid #22c55e;">
            <div style="color:#888;font-size:11px;text-transform:uppercase;">Take Profit</div>
            <div style="color:#22c55e;font-size:22px;font-weight:bold;">${signal['take_profit']:,.2f}</div>
          </div>
          <div style="flex:1;background:#111;border-radius:8px;padding:15px;border-left:4px solid #c9a84c;">
            <div style="color:#888;font-size:11px;text-transform:uppercase;">R:R Ratio</div>
            <div style="color:#c9a84c;font-size:22px;font-weight:bold;">1:{rr_ratio:.1f}</div>
          </div>
        </div>

        <div style="background:#111;border-radius:8px;padding:15px;">
          <div style="color:#888;font-size:12px;text-transform:uppercase;margin-bottom:10px;">All Confluence Factors</div>
          <ul style="margin:0;padding-left:20px;color:#e6edf3;line-height:1.8;">
            {reasons_html}
          </ul>
        </div>
      </div>

      <!-- Footer -->
      <div style="background:#0a0a0a;padding:15px 30px;border-top:1px solid {color}33;text-align:center;">
        <div style="color:{color};font-size:15px;font-weight:bold;">Score: {signal['score']}/9 — High confluence, execute at market or limit</div>
        <div style="color:#666;font-size:12px;margin-top:5px;">Confidence: {signal['confidence']}% | Always manage risk responsibly</div>
      </div>
    </div>
    <p style="color:#444;font-size:11px;text-align:center;margin-top:10px;">Trade Buttler Signal Engine</p>
  </div>
</body>
</html>"""
    return send_email(subject, html)

def send_test_email():
    """Send a test email to verify configuration."""
    subject = "✅ Trade Buttler — Email Test Successful"
    html = """
<!DOCTYPE html>
<html>
<body style="background:#0d1117;color:#e6edf3;font-family:Arial,sans-serif;padding:30px;">
  <div style="max-width:500px;margin:0 auto;background:#161b22;border:1px solid #c9a84c;border-radius:12px;padding:30px;text-align:center;">
    <h1 style="color:#c9a84c;">✅ Email Test Successful</h1>
    <p style="color:#8b949e;">Your Trade Buttler email alerts are configured correctly.</p>
    <p style="color:#8b949e;">You will receive trading signals at this address when setups form.</p>
    <hr style="border-color:#30363d;margin:20px 0;">
    <p style="color:#c9a84c;font-size:14px;">Trade Buttler Signal Engine</p>
  </div>
</body>
</html>"""
    return send_email(subject, html)
