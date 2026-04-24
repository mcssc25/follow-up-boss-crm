import { neighborhoodData } from './neighborhoodData.js';

let map;
let polygons = {};
let activeCardId = null;

const neighborhoodGrid = document.getElementById('neighborhoodGrid');
const searchInput = document.getElementById('searchInput');
const activeNeighborhoodName = document.getElementById('activeNeighborhoodName');
const modal = document.getElementById('modal');
const modalDetails = document.getElementById('modalDetails');
const closeBtn = document.querySelector('.close-btn');

function initMap() {
    map = L.map('neighborhood-map', {
        center: [30.295, -87.710],
        zoom: 12,
        zoomControl: false
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Render Polygons
    neighborhoodData.forEach(item => {
        if (item.polygon) {
            const poly = L.polygon(item.polygon, {
                color: '#0077b6',
                weight: 2,
                fillColor: '#0077b6',
                fillOpacity: 0.1,
                className: `neighborhood-poly-${item.id}`
            }).addTo(map);

            poly.on('mouseover', () => highlightNeighborhood(item.id, false));
            poly.on('mouseout', () => resetHighlight(item.id));
            poly.on('click', () => {
                document.getElementById(`card-${item.id}`).scrollIntoView({ behavior: 'smooth', block: 'center' });
                showModal(item);
            });

            polygons[item.id] = poly;
        }
    });
}

function highlightNeighborhood(id, scroll = true) {
    if (activeCardId === id) return;

    // Reset old highlight
    if (activeCardId && polygons[activeCardId]) {
        polygons[activeCardId].setStyle({ fillOpacity: 0.1, weight: 2 });
        const oldCard = document.getElementById(`card-${activeCardId}`);
        if (oldCard) oldCard.classList.remove('active');
    }

    activeCardId = id;
    const item = neighborhoodData.find(n => n.id === id);

    if (item && polygons[id]) {
        polygons[id].setStyle({ fillOpacity: 0.4, weight: 4 });
        const card = document.getElementById(`card-${id}`);
        if (card) {
            card.classList.add('active');
            if (scroll) {
                // Optional: scroll specifically when clicking map
            }
        }
        activeNeighborhoodName.innerText = item.name;
        map.panTo([item.lat, item.lng]);
    }
}

function resetHighlight(id) {
    // Only reset if it's not the "active" one based on scroll
    // For hover, we might want to keep the scroll-active one highlighted
}

function renderCards(data) {
    neighborhoodGrid.innerHTML = '';
    data.forEach(item => {
        const card = document.createElement('div');
        card.className = 'neighborhood-card';
        card.id = `card-${item.id}`;
        card.innerHTML = `
            <img src="${item.image}" alt="${item.name}" class="card-image">
            <div class="card-content">
                <span class="card-area">${item.area}</span>
                <h2 class="card-title">${item.name}</h2>
                <p class="card-price">${item.price_range}</p>
                <div class="card-tags">
                    ${item.on_golf_course ? '<span class="tag">Golf Course</span>' : ''}
                    ${item.has_pool ? '<span class="tag">Pool</span>' : ''}
                    ${item.is_gated ? '<span class="tag">Gated</span>' : ''}
                    ${item.styles.slice(0, 2).map(s => `<span class="tag">${s}</span>`).join('')}
                </div>
            </div>
        `;
        card.onclick = () => {
            highlightNeighborhood(item.id);
            showModal(item);
        };
        neighborhoodGrid.appendChild(card);

        // Intersection Observer for scroll-to-highlight
        observer.observe(card);
    });
}

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = parseInt(entry.target.id.split('-')[1]);
            highlightNeighborhood(id);
        }
    });
}, {
    root: neighborhoodGrid,
    threshold: 0.6
});

function showModal(item) {
    modalDetails.innerHTML = `
        <div class="modal-header">
            <h2 style="font-size: 2rem; margin-bottom: 20px; border-bottom: 2px solid #caf0f8; padding-bottom: 10px;">${item.name}</h2>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px;">
            <div>
                <h3 style="color: #0077b6; font-size: 0.9rem; text-transform: uppercase;">Price Range</h3>
                <p>${item.price_range}</p>
            </div>
            <div>
                <h3 style="color: #0077b6; font-size: 0.9rem; text-transform: uppercase;">Area</h3>
                <p>${item.area}</p>
            </div>
        </div>
        <div style="margin-bottom: 25px;">
            <h3 style="color: #0077b6; font-size: 0.9rem; text-transform: uppercase;">Amenities</h3>
            <p>${item.amenities}</p>
        </div>
        <div style="margin-bottom: 25px;">
            <h3 style="color: #0077b6; font-size: 0.9rem; text-transform: uppercase;">HOA Details</h3>
            <p><strong>Fees:</strong> ${item.hoa_fees}</p>
            <p><strong>Rules:</strong> ${item.hoa_rules}</p>
        </div>
        <div style="margin-bottom: 25px;">
            <h3 style="color: #0077b6; font-size: 0.9rem; text-transform: uppercase;">Description</h3>
            <p>${item.description}</p>
        </div>
    `;
    modal.style.display = 'block';
}

closeBtn.onclick = () => modal.style.display = 'none';
window.onclick = (e) => { if (e.target == modal) modal.style.display = 'none'; };

searchInput.oninput = (e) => {
    const term = e.target.value.toLowerCase();
    const filtered = neighborhoodData.filter(item => 
        item.name.toLowerCase().includes(term) || 
        item.amenities.toLowerCase().includes(term)
    );
    renderCards(filtered);
};

// Start
initMap();
renderCards(neighborhoodData);
if (neighborhoodData.length > 0) highlightNeighborhood(neighborhoodData[0].id);
