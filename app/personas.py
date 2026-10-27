"""Synthetic-but-grounded Indian population sampler.

Marginals are approximated from public sources (Census of India 2011 state
population shares and urbanisation rates, NSSO/PLFS-style age and income
bands).  Every persona is reproducible from (seed, audience, index).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, asdict, field

# state: (population share %, urban share %, language, anchor points [(city, lat, lon, is_city)])
STATES: dict[str, tuple[float, float, str, list[tuple[str, float, float, bool]]]] = {
    "Uttar Pradesh": (16.5, 22, "Hindi", [("Lucknow", 26.85, 80.95, True), ("Kanpur", 26.45, 80.33, True), ("Varanasi", 25.32, 82.97, True), ("Gorakhpur", 26.76, 83.37, False), ("Bareilly", 28.37, 79.43, False), ("Jhansi", 25.45, 78.57, False), ("Meerut", 28.98, 77.71, True), ("Prayagraj", 25.44, 81.85, False)]),
    "Maharashtra": (9.3, 45, "Marathi", [("Mumbai", 19.08, 72.88, True), ("Pune", 18.52, 73.86, True), ("Nagpur", 21.15, 79.09, True), ("Nashik", 20.0, 73.79, False), ("Aurangabad", 19.88, 75.34, False), ("Solapur", 17.66, 75.91, False)]),
    "Bihar": (8.6, 11, "Hindi", [("Patna", 25.59, 85.14, True), ("Gaya", 24.79, 85.0, False), ("Muzaffarpur", 26.12, 85.39, False), ("Bhagalpur", 25.25, 86.98, False), ("Purnia", 25.78, 87.47, False)]),
    "West Bengal": (7.5, 32, "Bengali", [("Kolkata", 22.57, 88.36, True), ("Siliguri", 26.73, 88.4, False), ("Durgapur", 23.52, 87.31, False), ("Bardhaman", 23.23, 87.86, False), ("Midnapore", 22.42, 87.32, False)]),
    "Madhya Pradesh": (6.0, 28, "Hindi", [("Indore", 22.72, 75.86, True), ("Bhopal", 23.26, 77.41, True), ("Jabalpur", 23.18, 79.99, False), ("Gwalior", 26.22, 78.18, False), ("Sagar", 23.84, 78.74, False), ("Rewa", 24.53, 81.3, False)]),
    "Tamil Nadu": (6.0, 48, "Tamil", [("Chennai", 13.08, 80.27, True), ("Coimbatore", 11.02, 76.96, True), ("Madurai", 9.93, 78.12, True), ("Tiruchirappalli", 10.8, 78.69, False), ("Salem", 11.66, 78.15, False), ("Tirunelveli", 8.73, 77.7, False)]),
    "Rajasthan": (5.7, 25, "Hindi", [("Jaipur", 26.91, 75.79, True), ("Jodhpur", 26.24, 73.02, True), ("Udaipur", 24.59, 73.71, False), ("Kota", 25.18, 75.83, False), ("Bikaner", 28.02, 73.31, False), ("Ajmer", 26.45, 74.64, False)]),
    "Karnataka": (5.0, 39, "Kannada", [("Bengaluru", 12.97, 77.59, True), ("Mysuru", 12.3, 76.64, True), ("Hubballi", 15.36, 75.12, False), ("Mangaluru", 12.91, 74.86, False), ("Belagavi", 15.85, 74.5, False), ("Kalaburagi", 17.33, 76.83, False)]),
    "Gujarat": (5.0, 43, "Gujarati", [("Ahmedabad", 23.02, 72.57, True), ("Surat", 21.17, 72.83, True), ("Vadodara", 22.31, 73.18, True), ("Rajkot", 22.3, 70.8, False), ("Bhavnagar", 21.76, 72.15, False)]),
    "Andhra Pradesh": (4.1, 30, "Telugu", [("Visakhapatnam", 17.69, 83.22, True), ("Vijayawada", 16.51, 80.65, True), ("Guntur", 16.31, 80.44, False), ("Tirupati", 13.63, 79.42, False), ("Kurnool", 15.83, 78.04, False), ("Nellore", 14.44, 79.99, False)]),
    "Telangana": (2.9, 39, "Telugu", [("Hyderabad", 17.39, 78.49, True), ("Warangal", 17.97, 79.59, False), ("Karimnagar", 18.44, 79.13, False), ("Nizamabad", 18.67, 78.1, False), ("Khammam", 17.25, 80.15, False)]),
    "Odisha": (3.5, 17, "Odia", [("Bhubaneswar", 20.3, 85.82, True), ("Cuttack", 20.46, 85.88, False), ("Sambalpur", 21.47, 83.97, False), ("Berhampur", 19.31, 84.79, False), ("Rourkela", 22.26, 84.85, False)]),
    "Kerala": (2.8, 48, "Malayalam", [("Kochi", 9.93, 76.27, True), ("Thiruvananthapuram", 8.52, 76.94, True), ("Kozhikode", 11.26, 75.78, True), ("Thrissur", 10.53, 76.21, False), ("Kollam", 8.89, 76.61, False)]),
    "Jharkhand": (2.7, 24, "Hindi", [("Ranchi", 23.34, 85.31, True), ("Jamshedpur", 22.8, 86.2, True), ("Dhanbad", 23.8, 86.43, False), ("Hazaribagh", 23.99, 85.36, False)]),
    "Assam": (2.6, 14, "Assamese", [("Guwahati", 26.14, 91.74, True), ("Dibrugarh", 27.47, 94.91, False), ("Silchar", 24.83, 92.78, False), ("Jorhat", 26.75, 94.2, False), ("Tezpur", 26.63, 92.79, False)]),
    "Punjab": (2.3, 37, "Punjabi", [("Ludhiana", 30.9, 75.86, True), ("Amritsar", 31.63, 74.87, True), ("Jalandhar", 31.33, 75.58, False), ("Patiala", 30.34, 76.39, False), ("Bathinda", 30.21, 74.95, False)]),
    "Chhattisgarh": (2.1, 23, "Hindi", [("Raipur", 21.25, 81.63, True), ("Bilaspur", 22.08, 82.14, False), ("Durg", 21.19, 81.28, False), ("Jagdalpur", 19.08, 82.02, False)]),
    "Haryana": (2.1, 35, "Hindi", [("Gurugram", 28.46, 77.03, True), ("Faridabad", 28.41, 77.32, True), ("Hisar", 29.15, 75.72, False), ("Rohtak", 28.9, 76.61, False), ("Karnal", 29.69, 76.99, False)]),
    "Delhi": (1.4, 97, "Hindi", [("New Delhi", 28.61, 77.21, True), ("Dwarka", 28.59, 77.05, True), ("Rohini", 28.74, 77.07, True)]),
    "Jammu & Kashmir": (1.0, 27, "Kashmiri", [("Srinagar", 34.08, 74.8, True), ("Jammu", 32.73, 74.86, True), ("Anantnag", 33.73, 75.15, False), ("Baramulla", 34.2, 74.34, False)]),
    "Uttarakhand": (0.8, 30, "Hindi", [("Dehradun", 30.32, 78.03, True), ("Haldwani", 29.22, 79.51, False), ("Haridwar", 29.95, 78.16, False)]),
    "Himachal Pradesh": (0.6, 10, "Hindi", [("Shimla", 31.1, 77.17, True), ("Mandi", 31.71, 76.93, False), ("Dharamshala", 32.22, 76.32, False)]),
    "Tripura": (0.3, 26, "Bengali", [("Agartala", 23.83, 91.28, True), ("Udaipur (Tripura)", 23.53, 91.48, False)]),
    "Meghalaya": (0.25, 20, "Khasi", [("Shillong", 25.58, 91.89, True), ("Tura", 25.51, 90.22, False)]),
    "Manipur": (0.2, 29, "Meitei", [("Imphal", 24.82, 93.94, True), ("Churachandpur", 24.33, 93.68, False)]),
    "Goa": (0.12, 62, "Konkani", [("Panaji", 15.5, 73.83, True), ("Margao", 15.27, 73.96, True)]),
}

REGION = {
    "Uttar Pradesh": "North", "Bihar": "East", "West Bengal": "East", "Madhya Pradesh": "Central",
    "Tamil Nadu": "South", "Rajasthan": "North", "Karnataka": "South", "Gujarat": "West",
    "Andhra Pradesh": "South", "Telangana": "South", "Odisha": "East", "Kerala": "South",
    "Jharkhand": "East", "Assam": "Northeast", "Punjab": "North", "Chhattisgarh": "Central",
    "Haryana": "North", "Delhi": "North", "Jammu & Kashmir": "North", "Uttarakhand": "North",
    "Himachal Pradesh": "North", "Tripura": "Northeast", "Meghalaya": "Northeast",
    "Manipur": "Northeast", "Goa": "West", "Maharashtra": "West",
}

AGE_BANDS = [((18, 24), 18), ((25, 34), 24), ((35, 44), 20), ((45, 59), 23), ((60, 78), 15)]
INCOME_BANDS = ["< ₹15k", "₹15–35k", "₹35–75k", "₹75k–2L", "> ₹2L"]  # monthly household
INCOME_W_RURAL = [55, 30, 11, 3.5, 0.5]
INCOME_W_URBAN = [25, 33, 24, 13, 5]

# occupation: (setting 'U'/'R'/'*', min_age, max_age, income band index range, weight, gender bias 'M'/'F'/None)
OCCUPATIONS = [
    ("farmer", "R", 22, 75, (0, 2), 22, None),
    ("agricultural labourer", "R", 18, 65, (0, 1), 14, None),
    ("dairy farmer", "R", 22, 70, (0, 2), 5, None),
    ("kirana shop owner", "*", 25, 70, (1, 3), 7, None),
    ("construction worker", "*", 18, 55, (0, 1), 7, "M"),
    ("ASHA health worker", "R", 22, 55, (0, 1), 2, "F"),
    ("government schoolteacher", "*", 25, 60, (2, 3), 4, None),
    ("homemaker", "*", 20, 75, (0, 4), 16, "F"),
    ("college student", "*", 18, 24, (0, 4), 9, None),
    ("retired", "*", 60, 78, (0, 3), 8, None),
    ("auto-rickshaw driver", "U", 20, 60, (0, 1), 4, "M"),
    ("food delivery partner", "U", 18, 40, (0, 1), 4, "M"),
    ("factory worker", "U", 18, 55, (0, 2), 6, None),
    ("software engineer", "U", 21, 45, (2, 4), 4, None),
    ("sales executive", "U", 21, 45, (1, 3), 4, None),
    ("government clerk", "U", 25, 60, (1, 3), 3, None),
    ("nurse", "U", 21, 55, (1, 2), 2, "F"),
    ("small business owner", "U", 25, 65, (1, 4), 5, None),
    ("startup founder", "U", 23, 45, (2, 4), 0.6, None),
    ("chartered accountant", "U", 24, 60, (3, 4), 1, None),
    ("domestic worker", "U", 18, 60, (0, 0), 3, "F"),
    ("gig worker (ride-hailing)", "U", 20, 50, (0, 1), 2, "M"),
    ("doctor", "U", 26, 70, (3, 4), 0.8, None),
    ("street vendor", "*", 18, 65, (0, 1), 4, None),
]

VALUES = ["family first", "frugal", "ambitious", "traditional", "status-conscious", "privacy-minded",
          "convenience-seeking", "community-minded", "sceptical of big companies", "early adopter",
          "religious", "environment-conscious", "value-for-money hunter", "proud of local brands"]

NAMES = {
    "Hindi": (["Ravi", "Amit", "Sunil", "Rahul", "Vikas", "Deepak", "Manoj", "Arjun", "Rohit", "Sanjay"],
              ["Pooja", "Sunita", "Neha", "Anjali", "Kavita", "Priya", "Rekha", "Shalini", "Meena", "Aarti"]),
    "Marathi": (["Sachin", "Ganesh", "Omkar", "Prasad", "Tushar", "Nilesh"], ["Snehal", "Ashwini", "Madhuri", "Pallavi", "Rutuja", "Shubhangi"]),
    "Bengali": (["Sourav", "Arnab", "Debashish", "Subhajit", "Partha", "Rajib"], ["Moumita", "Rituparna", "Sreya", "Payel", "Tanushree", "Mitali"]),
    "Tamil": (["Karthik", "Senthil", "Murugan", "Arun", "Vignesh", "Prabhu"], ["Lakshmi", "Divya", "Meenakshi", "Revathi", "Kavya", "Selvi"]),
    "Kannada": (["Manjunath", "Raghavendra", "Prajwal", "Basavaraj", "Darshan"], ["Shwetha", "Kavitha", "Ramya", "Sahana", "Bhavya"]),
    "Gujarati": (["Hardik", "Jignesh", "Bhavesh", "Kunal", "Nirav"], ["Hetal", "Krupa", "Dhara", "Komal", "Nisha"]),
    "Telugu": (["Srinivas", "Venkatesh", "Naveen", "Ramesh", "Sai Kiran", "Mahesh"], ["Lavanya", "Swathi", "Padma", "Sravani", "Haritha", "Anusha"]),
    "Odia": (["Subrat", "Bikash", "Debasis", "Pradeep"], ["Sasmita", "Lipika", "Mamata", "Smruti"]),
    "Malayalam": (["Anoop", "Jithin", "Sreejith", "Arun", "Bibin"], ["Anju", "Reshma", "Divya", "Athira", "Neethu"]),
    "Assamese": (["Bhaskar", "Pranjal", "Dhruba", "Hiren"], ["Pallabi", "Nandita", "Juri", "Barnali"]),
    "Punjabi": (["Gurpreet", "Harjeet", "Manpreet", "Jaspreet", "Amrinder"], ["Harpreet", "Simran", "Navjot", "Kiranjeet", "Jasleen"]),
    "Kashmiri": (["Imran", "Bilal", "Aamir", "Faisal"], ["Insha", "Mehvish", "Rukhsana", "Saima"]),
    "Khasi": (["Banshan", "Kyrshan", "Wanbok"], ["Ibapyntngen", "Daphisha", "Bashisha"]),
    "Meitei": (["Tomba", "Ibomcha", "Sanjoy"], ["Thoibi", "Bembem", "Sanatombi"]),
    "Konkani": (["Rohan", "Savio", "Pratik"], ["Sneha", "Shweta", "Melissa"]),
}

AUDIENCES = {
    "all": "All Indian adults (18+)",
    "urban_online": "Urban smartphone users",
    "genz": "Gen Z (18–27)",
    "rural": "Rural Bharat",
    "smb": "Small business owners & shopkeepers",
}


@dataclass
class Persona:
    id: int
    name: str
    gender: str
    age: int
    state: str
    region: str
    place: str
    urban: bool
    lat: float
    lon: float
    language: str
    occupation: str
    income: str
    income_idx: int
    values: list[str]
    apps: list[str]
    price_sensitivity: str
    tech_comfort: str
    neighbors: list[int] = field(default_factory=list)

    @property
    def age_group(self) -> str:
        a = self.age
        return "18–24" if a < 25 else "25–34" if a < 35 else "35–44" if a < 45 else "45–59" if a < 60 else "60+"

    def bio(self) -> str:
        setting = "urban" if self.urban else "rural"
        return (f"{self.name}, {self.age}, {'man' if self.gender == 'M' else 'woman'}, {self.occupation} "
                f"in/near {self.place}, {self.state} ({setting}). Household income {self.income}/month. "
                f"Speaks {self.language}. Values: {', '.join(self.values)}. "
                f"Uses: {', '.join(self.apps) if self.apps else 'basic phone, no apps'}. "
                f"Price sensitivity: {self.price_sensitivity}. Comfort with tech: {self.tech_comfort}.")

    def public(self) -> dict:
        d = asdict(self)
        d["age_group"] = self.age_group
        d["setting"] = "Urban" if self.urban else "Rural"
        return d


def _wchoice(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _sample_one(rng: random.Random, idx: int, audience: str) -> Persona | None:
    states = list(STATES)
    st = _wchoice(rng, states, [STATES[s][0] for s in states])
    share, urban_pct, lang, anchors = STATES[st]
    urban = rng.random() * 100 < urban_pct
    band = _wchoice(rng, AGE_BANDS, [w for _, w in AGE_BANDS])[0]
    age = rng.randint(*band)
    gender = rng.choice("MF")

    if audience == "rural" and urban:
        return None
    if audience == "urban_online":
        if not urban:
            return None
        if age > 55 and rng.random() < 0.7:
            return None
    if audience == "genz":
        if not 18 <= age <= 27:
            age = rng.randint(18, 27)

    w = INCOME_W_URBAN if urban else INCOME_W_RURAL
    if audience == "urban_online":
        w = [12, 30, 30, 19, 9]
    inc = _wchoice(rng, range(5), w)

    setting = "U" if urban else "R"
    occs = [o for o in OCCUPATIONS
            if (o[1] == "*" or o[1] == setting) and o[2] <= age <= o[3]
            and o[4][0] <= inc <= o[4][1] and (o[6] is None or o[6] == gender)]
    if audience == "smb":
        occs = [o for o in occs if o[0] in ("kirana shop owner", "small business owner", "street vendor", "dairy farmer")]
        if not occs:
            return None
    if not occs:
        occs = [o for o in OCCUPATIONS if o[0] in ("homemaker", "street vendor", "retired") and (o[6] is None or o[6] == gender)]
    occ = _wchoice(rng, occs, [o[5] for o in occs])[0]

    city_anchors = [a for a in anchors if a[3]] or anchors
    anchor = rng.choice(city_anchors if urban else anchors)
    spread = (0.22 if anchor[3] else 0.3) if urban else 0.7
    lat = anchor[1] + rng.gauss(0, spread)
    lon = anchor[2] + rng.gauss(0, spread)
    place = anchor[0]

    m, f = NAMES.get(lang, NAMES["Hindi"])
    name = rng.choice(m if gender == "M" else f)

    # traits
    ps_score = (4 - inc) + rng.random() * 1.5
    price_sens = "very high" if ps_score > 4 else "high" if ps_score > 3 else "medium" if ps_score > 1.8 else "low"
    tech = (2 if urban else 0) + (2 if age < 30 else 1 if age < 45 else 0) + (1 if inc >= 2 else 0)
    if occ in ("software engineer", "startup founder", "college student"):
        tech += 2
    if audience in ("urban_online", "genz"):
        tech += 1
    tech_comfort = "very high" if tech >= 5 else "high" if tech >= 4 else "medium" if tech >= 2 else "low"

    apps = ["WhatsApp"] if tech >= 1 or rng.random() < 0.6 else []
    pool = ["YouTube", "PhonePe", "Google Pay", "Instagram", "Facebook", "Paytm", "Flipkart", "Amazon",
            "Zomato", "Swiggy", "Blinkit", "Netflix", "JioCinema", "ShareChat", "Moj", "LinkedIn", "Meesho", "Uber", "Ola", "Rapido"]
    if apps:
        k = min(len(pool), max(0, tech + rng.randint(-1, 2)))
        weights = []
        for a in pool:
            wgt = 1.0
            if a in ("Zomato", "Swiggy", "Blinkit", "Uber", "Netflix", "LinkedIn") and not urban:
                wgt = 0.15
            if a in ("ShareChat", "Moj", "Meesho", "Facebook") and inc >= 3:
                wgt = 0.4
            if a in ("Instagram", "Moj") and age > 50:
                wgt = 0.3
            weights.append(wgt)
        chosen = set()
        for _ in range(k * 2):
            if len(chosen) >= k:
                break
            chosen.add(_wchoice(rng, pool, weights))
        apps += sorted(chosen)

    vals = rng.sample(VALUES, 2)
    if inc <= 1 and "frugal" not in vals and rng.random() < 0.4:
        vals[0] = "frugal"
    if tech >= 5 and rng.random() < 0.4 and "early adopter" not in vals:
        vals[1] = "early adopter"
    if tech < 3 and "early adopter" in vals:
        vals[vals.index("early adopter")] = rng.choice(["traditional", "community-minded", "family first"])
        if vals[0] == vals[1]:
            vals[1] = "value-for-money hunter" if vals[0] != "value-for-money hunter" else "religious"

    return Persona(id=idx, name=name, gender=gender, age=age, state=st, region=REGION[st], place=place,
                   urban=urban, lat=round(lat, 3), lon=round(lon, 3), language=lang, occupation=occ,
                   income=INCOME_BANDS[inc], income_idx=inc, values=vals, apps=apps,
                   price_sensitivity=price_sens, tech_comfort=tech_comfort)


def sample_population(n: int, audience: str = "all", seed: int = 42) -> list[Persona]:
    rng = random.Random(f"{seed}:{audience}")
    out: list[Persona] = []
    tries = 0
    while len(out) < n and tries < n * 200:
        tries += 1
        p = _sample_one(rng, len(out), audience)
        if p:
            out.append(p)
    build_social_graph(out, rng)
    return out


def build_social_graph(people: list[Persona], rng: random.Random, local: int = 3, peer: int = 1, far: int = 1) -> None:
    """Small-world, homophilous graph: local ties (same state & setting),
    peer ties (same age group anywhere) and a few random long-range ties."""
    by_state: dict[tuple[str, bool], list[int]] = {}
    by_age: dict[str, list[int]] = {}
    for p in people:
        by_state.setdefault((p.state, p.urban), []).append(p.id)
        by_age.setdefault(p.age_group, []).append(p.id)
    edges: set[tuple[int, int]] = set()

    def add(a: int, b: int):
        if a != b:
            edges.add((min(a, b), max(a, b)))

    n = len(people)
    for p in people:
        local_pool = by_state[(p.state, p.urban)]
        if len(local_pool) < 4:
            local_pool = [q.id for q in people if q.state == p.state] or local_pool
        local_pool = sorted(local_pool, key=lambda j: (people[j].lat - p.lat) ** 2 + (people[j].lon - p.lon) ** 2)[1:local * 3 + 1]
        for j in rng.sample(local_pool, min(local, len(local_pool))):
            add(p.id, j)
        for j in rng.sample(by_age[p.age_group], min(peer, len(by_age[p.age_group]))):
            add(p.id, j)
        for _ in range(far):
            add(p.id, rng.randrange(n))
    for p in people:
        p.neighbors = []
    for a, b in edges:
        people[a].neighbors.append(b)
        people[b].neighbors.append(a)
