document.getElementById('lead-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const form = e.target;
    const submitBtn = form.querySelector('.btn-submit');
    const originalBtnText = submitBtn.innerHTML;
    
    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = 'Sending...';
    
    const firstName = form.querySelector('input[type="text"]').value;
    const email = form.querySelector('input[type="email"]').value;
    const timeline = form.querySelector('select').value;
    
    // Replace with your actual API Key from CRM Admin
    const API_KEY = 'your_api_key_here';
    if (API_KEY === 'your_api_key_here') {
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
            // Success! 
            submitBtn.innerHTML = 'Success! Check your Email';
            submitBtn.style.background = '#2ecc71';
            
            // Redirect to the PDF or show success message after 2 seconds
            setTimeout(() => {
                window.location.href = 'relocation-guide-pdf.html'; 
            }, 2000);
        } else {
            const error = await response.json();
            console.error('API Error:', error);
            alert('Something went wrong. Please try again.');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    } catch (err) {
        console.error('Network Error:', err);
        alert('Could not connect to the CRM. Please check your internet.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
});
