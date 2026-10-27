"""Example scenarios and historical back-tests.

Back-test cases are framed exactly as the public saw them *before* the outcome
was known (date + announcement text). The real outcome is only revealed in the
UI after the simulation finishes, so viewers can judge the call themselves.
"""

EXAMPLES = [
    {
        "id": "rain_fee",
        "title": "₹15 'rain surge' on food delivery",
        "audience": "urban_online",
        "proposal": "A major food-delivery app announces a flat ₹15 'rain surge fee' on every order placed during heavy rain, "
                    "saying the money goes directly to delivery partners riding in unsafe conditions.",
    },
    {
        "id": "upi_fee",
        "title": "0.3% fee on UPI payments above ₹2,000",
        "audience": "all",
        "proposal": "The government proposes a 0.3% transaction fee on person-to-merchant UPI payments above ₹2,000, "
                    "paid by the customer, to fund cyber-fraud protection and keep UPI infrastructure free for small payments.",
    },
    {
        "id": "4day_week",
        "title": "4-day work week for IT services",
        "audience": "urban_online",
        "proposal": "India's largest IT-services firms jointly announce a 4-day, 40-hour work week (10 hours a day) "
                    "for all employees from next quarter, with no change in salary.",
    },
    {
        "id": "ev_scooter",
        "title": "₹49,999 EV scooter with battery-on-rent",
        "audience": "all",
        "proposal": "An Indian EV startup launches a ₹49,999 electric scooter where you rent the battery for ₹1,199/month "
                    "with unlimited swaps at 3,000 kirana stores across India.",
    },
]

BACKTESTS = [
    {
        "id": "free_basics",
        "title": "Facebook Free Basics (2015)",
        "date": "December 2015",
        "audience": "urban_online",
        "proposal": "Facebook is promoting 'Free Basics' in India with Reliance Communications: free access to a limited set of "
                    "websites and services chosen by Facebook and partners, with no data charges. Facebook says it will "
                    "connect the next billion Indians. Critics say it violates net neutrality. TRAI has opened a public "
                    "consultation on differential pricing for data.",
        "actual": "rejected",
        "actual_text": "There was a large public backlash led by the #SaveTheInternet net-neutrality campaign. On 8 Feb 2016, "
                       "TRAI banned discriminatory pricing for data services and Free Basics was shut down in India.",
    },
    {
        "id": "zomato_fee",
        "title": "Zomato's per-order platform fee (2023)",
        "date": "August 2023",
        "audience": "urban_online",
        "proposal": "Zomato introduces a ₹2 'platform fee' on every food-delivery order, regardless of order value, on top of "
                    "delivery fees and taxes. Zomato Gold members are also charged.",
        "actual": "accepted",
        "actual_text": "Users complained on social media but kept ordering. Zomato raised the fee about six times in a year, "
                       "reaching ₹10 per order in October 2024, and Swiggy followed with a similar fee.",
    },
    {
        "id": "reels",
        "title": "Instagram Reels after the TikTok ban (2020)",
        "date": "July 2020",
        "audience": "genz",
        "proposal": "Days after the Indian government banned TikTok and 58 other Chinese apps, Instagram launches 'Reels' in "
                    "India: 15-second short videos with music, effects and an Explore feed, built into the Instagram app.",
        "actual": "embraced",
        "actual_text": "Indian users and creators took it up quickly. India was one of the first countries to get Reels, which "
                       "became Instagram's core short-video format worldwide within weeks.",
    },
]

OUTCOME_LABELS = {
    "rejected": "Rejected / backlash",
    "accepted": "Grudgingly accepted",
    "embraced": "Embraced",
}


def classify(net_sentiment: float, adoption: float) -> str:
    """Map simulated aggregate to an outcome bucket.
    net_sentiment in [-2, 2], adoption in [0, 1]."""
    if adoption >= 0.6 and net_sentiment >= 0.35:
        return "embraced"
    if adoption >= 0.45:
        return "accepted"
    return "rejected"
