"""
Event management endpoints: CRUD, attendee RSVP, and event listing for organizations.

- Create, read, update, delete events (admins, organizers)
- RSVP/registration for members
- List events filtered by org, date, rsvp status
- Includes RBAC and OpenAPI docs.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date

from src.api.models import Event, User, Org
from src.api.schemas import (
    EventCreate, EventOut, APIResponse
)
from src.api.auth import get_db, get_current_user, rbac_required

router = APIRouter(prefix="/events", tags=["Events"])

# PUBLIC_INTERFACE
@router.post("/", response_model=EventOut, summary="Create event")
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Create a new event for an organization.
    """
    org = db.query(Org).filter(Org.id == event_in.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    event = Event(
        org_id=event_in.org_id,
        title=event_in.title,
        description=event_in.description,
        date=event_in.date,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        location=event_in.location,
        capacity=event_in.capacity,
        fee=event_in.fee,
        organizer_id=event_in.organizer_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return EventOut(
        id=event.id,
        org_id=event.org_id,
        title=event.title,
        description=event.description,
        date=event.date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        capacity=event.capacity,
        fee=event.fee,
        organizer_id=event.organizer_id,
        attendees=[],
        qr_code_url=event.qr_code_url,
    )

# PUBLIC_INTERFACE
@router.get("/", response_model=List[EventOut], summary="List events")
def list_events(
    db: Session = Depends(get_db),
    org_id: Optional[int] = Query(None, description="Organization ID"),
    upcoming_only: Optional[bool] = Query(False, description="Only include upcoming events"),
    attendee_user_id: Optional[int] = Query(None, description="List only events user RSVP'd to"),
):
    """
    List events, filtered by org, upcoming, or RSVP'd status for user.
    """
    qset = db.query(Event)
    if org_id:
        qset = qset.filter(Event.org_id == org_id)
    if upcoming_only:
        qset = qset.filter(Event.date >= date.today())
    events = qset.options(joinedload(Event.attendees)).all()
    result = []
    for e in events:
        if attendee_user_id:
            if not any(u.id == attendee_user_id for u in e.attendees):
                continue
        result.append(EventOut(
            id=e.id,
            org_id=e.org_id,
            title=e.title,
            description=e.description,
            date=e.date,
            start_time=e.start_time,
            end_time=e.end_time,
            location=e.location,
            capacity=e.capacity,
            fee=e.fee,
            organizer_id=e.organizer_id,
            attendees=[u.id for u in e.attendees],
            qr_code_url=e.qr_code_url
        ))
    return result

# PUBLIC_INTERFACE
@router.get("/{event_id}", response_model=EventOut, summary="Get event details")
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).options(joinedload(Event.attendees)).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventOut(
        id=event.id,
        org_id=event.org_id,
        title=event.title,
        description=event.description,
        date=event.date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        capacity=event.capacity,
        fee=event.fee,
        organizer_id=event.organizer_id,
        attendees=[u.id for u in event.attendees],
        qr_code_url=event.qr_code_url
    )

# PUBLIC_INTERFACE
@router.put("/{event_id}", response_model=EventOut, summary="Update event")
def update_event(
    event_id: int,
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for attr in [
        "org_id", "title", "description", "date", "start_time", "end_time",
        "location", "capacity", "fee", "organizer_id"
    ]:
        setattr(event, attr, getattr(event_in, attr))
    db.commit()
    db.refresh(event)
    return EventOut(
        id=event.id,
        org_id=event.org_id,
        title=event.title,
        description=event.description,
        date=event.date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        capacity=event.capacity,
        fee=event.fee,
        organizer_id=event.organizer_id,
        attendees=[u.id for u in event.attendees],
        qr_code_url=event.qr_code_url
    )

# PUBLIC_INTERFACE
@router.delete("/{event_id}", response_model=APIResponse, summary="Delete event")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    return APIResponse(success=True, message="Event deleted.")

# PUBLIC_INTERFACE
@router.post("/{event_id}/rsvp", response_model=APIResponse, summary="RSVP/register for event")
def rsvp_event(
    event_id: int,
    rsvp_status: str = Body(..., embed=True, description="RSVP status: going, maybe, not_going"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RSVP or register for an event.
    """
    event = db.query(Event).options(joinedload(Event.attendees)).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if rsvp_status not in ["going", "maybe", "not_going"]:
        raise HTTPException(status_code=400, detail="Invalid RSVP status")
    already_rsvpd = any(u.id == current_user.id for u in event.attendees)
    if rsvp_status == "going":
        # Add to attendees if not already in list
        if not already_rsvpd:
            if event.capacity and len(event.attendees) >= event.capacity:
                raise HTTPException(status_code=403, detail="Event is full.")
            event.attendees.append(current_user)
            db.commit()
        return APIResponse(success=True, message="RSVP confirmed")
    else:
        # For not_going or maybe, remove if present
        if already_rsvpd:
            event.attendees = [u for u in event.attendees if u.id != current_user.id]
            db.commit()
        return APIResponse(success=True, message=f"RSVP set to {rsvp_status}")

# PUBLIC_INTERFACE
@router.get("/by_user/{user_id}", response_model=List[EventOut], summary="List events a user RSVP'd")
def events_user_rsvp(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    List events a user is RSVP'd to (registered as attendee).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    events = user.events_attending
    return [
        EventOut(
            id=e.id,
            org_id=e.org_id,
            title=e.title,
            description=e.description,
            date=e.date,
            start_time=e.start_time,
            end_time=e.end_time,
            location=e.location,
            capacity=e.capacity,
            fee=e.fee,
            organizer_id=e.organizer_id,
            attendees=[u.id for u in e.attendees],
            qr_code_url=e.qr_code_url
        )
        for e in events
    ]
