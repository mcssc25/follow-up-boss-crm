import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def process_incoming_message(page_id, platform, sender_id, message_text):
    """Process an incoming social DM — match keywords and execute actions.

    Stubbed — full implementation in Task 6.
    """
    logger.info(
        "Received message: page=%s platform=%s sender=%s text=%s",
        page_id, platform, sender_id, message_text[:100],
    )
