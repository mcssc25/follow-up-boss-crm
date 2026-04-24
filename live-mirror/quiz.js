/**
 * quiz.js — Condo Quiz Landing Page
 *
 * Handles filter selection, CRM lead submission, and redirect to condos page.
 */

const BASE = '/condos/';
const API_URL = 'https://crm.bigbeachal.com/api/leads/';
const API_KEY = 'API_KEY_REDACTED_FROM_MIRROR';

// --- Quiz selections (Sets) ---
const selections = {
  price: new Set(),
  pool: new Set(),
  rental: new Set(),
  location: new Set(),
  beachfront: new Set(),
  amenity: new Set()
};

// --- Tag mapping: filter value → CRM tag name ---
const TAG_MAP = {
  'under-400': 'Budget: Under $400k',
  '400-700': 'Budget: $400k-$700k',
  'above-700': 'Budget: $700k+',
  'outdoor': 'Wants: Outdoor Pool',
  'indoor': 'Wants: Indoor Pool',
  'lazy': 'Wants: Lazy River',
  'multiple': 'Wants: Multiple Pools',
  'yes': 'Wants: STR Allowed',
  'pet': 'Wants: Pet Friendly',
  'fort-morgan': 'Area: Fort Morgan',
  'gulf-shores': 'Area: Gulf Shores',
  'orange-beach': 'Area: Orange Beach',
  'fitness': 'Wants: Fitness Center',
  'sauna': 'Wants: Sauna/Steam Room',
  'parking': 'Wants: Covered Parking',
  'hottub': 'Wants: Hot Tub/Spa',
  'grill': 'Wants: Grilling Area',
  'tennis': 'Wants: Tennis Courts',
  'pickleball': 'Wants: Pickleball',
  'basketball': 'Wants: Basketball',
  'kiddiepool': 'Wants: Kiddie Pool',
  'boardwalk': 'Wants: Boardwalk',
  'splashpad': 'Wants: Splash Pad/Slide',
  'gameroom': 'Wants: Game Room',
  'dock': 'Wants: Private Dock',
  'elevator': 'Wants: Elevator Access',
  'bf-yes': 'Wants: Beachfront',
  'bf-no': 'OK: Across Street'
};

// --- Init quiz button toggles ---
function initQuizButtons() {
  const groups = [
    { id: 'quiz-price', key: 'price' },
    { id: 'quiz-pool', key: 'pool' },
    { id: 'quiz-rental', key: 'rental' },
    { id: 'quiz-location', key: 'location' },
    { id: 'quiz-beachfront', key: 'beachfront' },
    { id: 'quiz-amenity', key: 'amenity' }
  ];

  groups.forEach(({ id, key }) => {
    const container = document.getElementById(id);
    if (!container) return;
    container.querySelectorAll('.quiz-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const value = btn.dataset.value;
        // "No Preference" clears other selections in this group
        if (value === 'none') {
          selections[key].clear();
          container.querySelectorAll('.quiz-btn').forEach(b => b.classList.remove('active'));
          selections[key].add('none');
          btn.classList.add('active');
          return;
        }
        // Clicking a real option removes "none"
        if (selections[key].has('none')) {
          selections[key].delete('none');
          container.querySelector('[data-value="none"]')?.classList.remove('active');
        }
        if (selections[key].has(value)) {
          selections[key].delete(value);
          btn.classList.remove('active');
        } else {
          selections[key].add(value);
          btn.classList.add('active');
        }
      });
    });
  });
}

// --- Build CRM tags from selections ---
function buildTags() {
  const tags = ['Condo'];
  for (const values of Object.values(selections)) {
    for (const v of values) {
      if (TAG_MAP[v]) tags.push(TAG_MAP[v]);
    }
  }
  return tags;
}

// --- Build redirect URL with filter params ---
function buildRedirectURL(firstName) {
  const params = new URLSearchParams();

  if (selections.location.size > 0) params.set('location', [...selections.location].join(','));
  if (selections.price.size > 0) params.set('price', [...selections.price].join(','));
  if (selections.beachfront.size > 0) params.set('beachfront', [...selections.beachfront].map(v => v.replace('bf-', '')).join(','));
  if (selections.pool.size > 0 && !selections.pool.has('none')) params.set('pool', [...selections.pool].join(','));
  if (selections.rental.size > 0) params.set('rental', [...selections.rental].join(','));
  if (selections.amenity.size > 0) params.set('amenity', [...selections.amenity].join(','));
  if (firstName) params.set('name', firstName);

  const qs = params.toString();
  return `${BASE}${qs ? '?' + qs : ''}`;
}

// --- Submit to CRM ---
async function submitLead(firstName, lastName, email, resultsURL) {
  const tags = buildTags();

  const body = {
    first_name: firstName,
    last_name: lastName,
    email: email,
    source: 'landing_page',
    source_detail: 'condo-quiz',
    tags: tags,
    results_url: resultsURL,
    campaign_id: 2
  };

  try {
    const resp = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': API_KEY
      },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      console.warn('CRM API returned', resp.status);
    }
  } catch (err) {
    console.warn('CRM submission failed:', err);
  }
}

// --- Form submit handler ---
function initForm() {
  const form = document.getElementById('quiz-form');
  const submitBtn = document.getElementById('submit-btn');
  const errorEl = document.getElementById('form-error');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.classList.add('hidden');

    const firstName = document.getElementById('first_name').value.trim();
    const lastName = document.getElementById('last_name').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!firstName || !email) {
      errorEl.textContent = 'Please enter your name and email.';
      errorEl.classList.remove('hidden');
      return;
    }

    // Disable button while submitting
    submitBtn.disabled = true;
    submitBtn.textContent = 'Finding your matches...';
    submitBtn.classList.add('opacity-70');

    const redirectURL = buildRedirectURL(firstName);
    const fullResultsURL = new URL(redirectURL, window.location.origin).href;

    // Submit to CRM, then redirect
    await submitLead(firstName, lastName, email, fullResultsURL);
    window.location.href = redirectURL;
  });
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
  initQuizButtons();
  initForm();
});
