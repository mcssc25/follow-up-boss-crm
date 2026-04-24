const fs = require('fs');

const index_path = "c:\\Users\\daved\\AntiGravity Projects\\follow up boss\\normal buyers\\deploy\\index.html";
const csv_path = "C:\\Users\\daved\\AntiGravity Projects\\follow up boss\\normal buyers\\Default_MLS_Defined_Spreadsheet (1).csv";

const content = fs.readFileSync(index_path, 'utf8');
const nameRegex = /name:\s*["']([^"']+)["']/g;

const existingNames = new Set();
let match;
while ((match = nameRegex.exec(content)) !== null) {
    if (match[1].trim() !== '') {
        existingNames.add(match[1].toLowerCase().trim());
    }
}
console.log("Existing names mapping: ", existingNames);

const csvContent = fs.readFileSync(csv_path, 'utf8');
const rows = csvContent.split('\n');
const headers = rows[0].split(',');
const subIndex = headers.findIndex(h => h.includes('Subdivsn'));
const cityIndex = headers.findIndex(h => h.includes('City'));

if (subIndex === -1 || cityIndex === -1) {
    console.log("Couldn't find columns");
    process.exit(1);
}

const counts = {};

for (let i = 1; i < rows.length; i++) {
    const row = rows[i].split(',');
    if (row.length > Math.max(subIndex, cityIndex)) {
        const sub = row[subIndex].replace(/["']/g, '').trim();
        const city = row[cityIndex].replace(/["']/g, '').trim();
        
        if (city.toLowerCase() === 'gulf shores' && sub) {
            counts[sub] = (counts[sub] || 0) + 1;
        }
    }
}

const missing = [];
for (const [sub, count] of Object.entries(counts)) {
    let isMapped = false;
    for (const existing of existingNames) {
        if (existing.length > 3 && (sub.toLowerCase().includes(existing) || existing.includes(sub.toLowerCase()))) {
            isMapped = true;
            break;
        }
    }
    if (!isMapped && sub !== "None" && sub !== "Not in a Subdivision" && !sub.includes("Oyster Bay Village")) {
        missing.push({ sub, count });
    }
}

missing.sort((a, b) => b.count - a.count);

console.log("\nTop Missing Subdivisions in Gulf Shores:");
for (let i = 0; i < Math.min(30, missing.length); i++) {
    console.log(`- ${missing[i].sub} (${missing[i].count} listings)`);
}
