"""
QR code endpoints for event check-in and registration.

- Generate event QR code (for event registration/check-in)
- Download QR as PNG (optionally attach event/user info)
"""
from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session
import qrcode
import io
import base64

from src.api.models import Event
from src.api.auth import get_db

router = APIRouter(prefix="/qrcodes", tags=["Events"])

# PUBLIC_INTERFACE
@router.get("/event/{event_id}", summary="Get event QR code (PNG, base64)")
def generate_event_qr(
    event_id: int,
    size: int = 256,
    db: Session = Depends(get_db)
):
    """
    Returns QR code (base64 PNG) for the event, encoding event_id for check-in.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    qr_data = f"event_id:{event.id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    encoded_png = base64.b64encode(buf.getvalue()).decode('utf-8')
    return {"qr_code_base64": encoded_png, "event_id": event.id}

# PUBLIC_INTERFACE
@router.get("/event/{event_id}/download", summary="Download event QR code (PNG)")
def download_event_qr(
    event_id: int,
    size: int = 256,
    db: Session = Depends(get_db)
):
    """
    Downloads the event QR code as PNG.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    qr_data = f"event_id:{event.id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png", headers={
        "Content-Disposition": f'attachment; filename="event_{event.id}.png"'
    })
