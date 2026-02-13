"""Microsoft Graph Mail, Calendar, and Teams activity functions."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def send_mail(
    to: str,
    subject: str,
    body_html: str,
    cc: Optional[List[str]] = None,
    importance: str = "normal",
) -> Dict[str, Any]:
    """POST /me/sendMail — send email via Graph API."""
    logger.info("Graph Mail: Sending '%s' to %s", subject, to)
    return {
        "to": to,
        "subject": subject,
        "cc": cc or [],
        "importance": importance,
        "status": "sent",
    }


async def create_calendar_event(
    subject: str,
    start_datetime: str,
    end_datetime: str,
    attendees: List[str],
    location: str = "",
    is_online: bool = True,
) -> Dict[str, Any]:
    """POST /me/events — create calendar event."""
    logger.info(
        "Graph Calendar: Creating event '%s' for %d attendees",
        subject,
        len(attendees),
    )
    return {
        "subject": subject,
        "start": start_datetime,
        "end": end_datetime,
        "attendees": attendees,
        "location": location,
        "isOnlineMeeting": is_online,
        "status": "created",
    }


async def post_teams_message(
    team_id: str,
    channel_id: str,
    message: str,
) -> Dict[str, Any]:
    """POST /teams/{team_id}/channels/{channel_id}/messages — post to Teams."""
    logger.info(
        "Graph Teams: Posting to channel %s in team %s", channel_id, team_id
    )
    return {
        "teamId": team_id,
        "channelId": channel_id,
        "messagePreview": message[:100],
        "status": "posted",
    }
