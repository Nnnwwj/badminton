from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentTime, CurrentUser, DatabaseSession
from app.models import GameSession
from app.schemas import SessionCreate, SessionResponse
from app.services.sessions import (
    JoinConflictError,
    SessionNotFoundError,
    count_joined_participants,
    create_game_session,
    join_session,
    list_sessions_with_participant_counts,
)


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_response(
    game_session: GameSession,
    participant_count: int,
) -> SessionResponse:
    return SessionResponse(
        id=game_session.id,
        creator_id=game_session.creator_id,
        start_at=game_session.start_at,
        end_at=game_session.end_at,
        area=game_session.area,
        venue=game_session.venue,
        format=game_session.format,
        purpose=game_session.purpose,
        level_label=game_session.level_label,
        capacity=game_session.capacity,
        status=game_session.status,
        created_at=game_session.created_at,
        participant_count=participant_count,
        spots_remaining=max(game_session.capacity - participant_count, 0),
    )


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    db: DatabaseSession,
    _current_user: CurrentUser,
) -> list[SessionResponse]:
    return [
        _session_response(game_session, participant_count)
        for game_session, participant_count in list_sessions_with_participant_counts(
            db
        )
    ]


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: SessionCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> SessionResponse:
    game_session = create_game_session(db, current_user.id, payload)
    participant_count = count_joined_participants(db, game_session.id)
    return _session_response(game_session, participant_count)


@router.post("/{session_id}/join", response_model=SessionResponse)
def join_existing_session(
    session_id: str,
    db: DatabaseSession,
    current_user: CurrentUser,
    now: CurrentTime,
) -> SessionResponse:
    try:
        result = join_session(db, session_id, current_user.id, now)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "session_not_found",
                "message": "Activity does not exist",
            },
        ) from None
    except JoinConflictError as error:
        messages = {
            "already_joined": "User has already joined this activity",
            "session_full": "Activity has no remaining spots",
            "session_ended": "Activity has ended",
            "session_unavailable": "Activity is not open for registration",
        }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "message": messages[error.code]},
        ) from None

    return _session_response(
        result.game_session,
        result.participant_count,
    )
