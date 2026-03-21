def render_campaign_email(body, contact, agent):
    """Replace merge field placeholders with actual contact/agent values."""
    replacements = {
        '{{first_name}}': contact.first_name,
        '{{last_name}}': contact.last_name,
        '{{full_name}}': f"{contact.first_name} {contact.last_name}",
        '{{agent_name}}': agent.get_full_name() or agent.username,
        '{{agent_phone}}': getattr(agent, 'phone', ''),
        '{{agent_email}}': agent.email,
    }
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value or '')
    return body
