document.getElementById('lead-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const form = e.target;
    const submitBtn = form.querySelector('.btn-submit');
    const originalBtnText = submitBtn.innerHTML;
    const successPanel = document.getElementById('form-success');

    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = 'Sending&hellip;';

    // Read by name (robust to layout changes)
    const firstName = form.querySelector('input[name="first_name"]').value.trim();
    const email = form.querySelector('input[name="email"]').value.trim();
    const timeline = form.querySelector('select[name="timeline"]').value;

    // Replace with the real API Key from CRM Admin (/admin/api/apikey/) before deploying
    const API_KEY = 'API_KEY_REDACTED_FROM_MIRROR';
    if (API_KEY === 'API_KEY_REDACTED_FROM_MIRROR') {
        console.error('[relocation-guide] API_KEY placeholder not replaced — form submissions will fail. Set the real API key in api_connection.js before deploying.');
    }

    const payload = {
        first_name: firstName,
        email: email,
        source: 'lead_magnet_relocation',
        tags: ['relocation', 'relocation-guide', `timeline-${timeline}`],
        campaign_name: 'Track 1 — Relocation Welcome',
        source_detail: `Timeline preference: ${timeline}`,
        utm_source: 'website',
        utm_campaign: 'track1-relocation',
        utm_content: 'relocation-guide-pdf'
    };

    try {
        const response = await fetch('https://crm.bigbeachal.com/api/leads/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Api-Key': API_KEY
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            // Hide the form, show the success panel, then redirect to subdivisions
            form.hidden = true;
            if (successPanel) {
                successPanel.hidden = false;
                if (window.lucide) lucide.createIcons();
                successPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            setTimeout(() => {
                window.location.href = 'https://bigbeachal.com/gulfshoressubdivisions/?utm_source=relocation-guide&utm_medium=post-signup-redirect&utm_campaign=track1-relocation';
            }, 2800);
        } else {
            const error = await response.json().catch(() => ({}));
            console.error('API Error:', response.status, error);
            alert('Something went wrong submitting the form. Please try again or email us directly.');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
            if (window.lucide) lucide.createIcons();
        }
    } catch (err) {
        console.error('Network Error:', err);
        alert('Could not connect. Please check your internet and try again.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
        if (window.lucide) lucide.createIcons();
    }
});
