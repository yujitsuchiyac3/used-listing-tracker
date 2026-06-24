"""メール送信。

HTML 内のリモート画像 (<img src="http...">) をダウンロード・縮小して
インライン添付(CID)に差し替え、画像が常に表示されるメールを組み立てて
SMTP で送信する。SMTP 設定は環境変数から読む。

環境変数:
  SMTP_HOST, SMTP_PORT(既定465), SMTP_USER, SMTP_PASS,
  MAIL_FROM(既定 SMTP_USER), MAIL_TO(カンマ区切り)
"""
from __future__ import annotations

import io
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Optional, Tuple

import requests

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

UA = {"User-Agent": "Mozilla/5.0 (compatible; used-listing-tracker/1.0)"}
IMG_SRC_RE = re.compile(r'<img\b[^>]*?\bsrc="([^"]+)"', re.I)


def embed_images(html: str, max_width: int = 130) -> Tuple[str, list]:
    """HTML 内の http(s) 画像を CID インライン添付に変換する。

    返り値: (置換後HTML, [(cid, mime_subtype, bytes), ...])
    取得/縮小に失敗した画像は元のリモートURLのまま残す。
    """
    cache = {}      # url -> cid (同一URLは1添付に集約)
    attachments = []

    def repl(match):
        whole = match.group(0)
        url = match.group(1)
        if not url.lower().startswith("http"):
            return whole
        if url in cache:
            cid = cache[url]
        else:
            data = _download_thumb(url, max_width)
            if data is None:
                return whole  # 失敗時はリモートのまま
            cid_token = make_msgid(domain="ult.local")[1:-1]  # 角括弧除去
            cache[url] = cid_token
            cid = cid_token
            attachments.append((cid, "jpeg", data))
        return whole.replace(f'src="{url}"', f'src="cid:{cid}"')

    return IMG_SRC_RE.sub(repl, html), attachments


def _download_thumb(url: str, max_width: int) -> Optional[bytes]:
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        if not _HAS_PIL:
            return r.content
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        if im.width > max_width:
            h = int(im.height * max_width / im.width)
            im = im.resize((max_width, h))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72)
        return buf.getvalue()
    except Exception:
        return None


def build_message(subject: str, html: str, text: str,
                  mail_from: str, mail_to: list) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(mail_to)
    msg.set_content(text)  # プレーンテキスト代替

    embedded_html, attachments = embed_images(html)
    # cid:xxx は <xxx> を参照するので add_alternative 後に related で添付
    msg.add_alternative(embedded_html, subtype="html")
    html_part = msg.get_payload()[-1]
    for cid, subtype, data in attachments:
        html_part.add_related(data, "image", subtype, cid=f"<{cid}>")
    return msg


def send(subject: str, html: str, text: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    mail_from = os.environ.get("MAIL_FROM") or user
    mail_to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not mail_to:
        raise RuntimeError("MAIL_TO が未設定です")

    msg = build_message(subject, html, text, mail_from, mail_to)
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            if user:
                s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=context)
            if user:
                s.login(user, password)
            s.send_message(msg)
