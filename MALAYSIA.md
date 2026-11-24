# Malaysia-wide Myroomzie business-contact research

Scope: **all Malaysian states and the three federal territories**, not just Petaling Jaya/Subang Jaya. Research publicly posted business contact details; do not infer unverified personal emails.

## Suggested research locations
Johor (Johor Bahru, Batu Pahat); Kedah (Alor Setar, Sungai Petani); Kelantan (Kota Bharu); Melaka (Melaka); Negeri Sembilan (Seremban, Nilai); Pahang (Kuantan, Temerloh); Perak (Ipoh, Taiping); Perlis (Kangar); Penang (George Town, Butterworth); Sabah (Kota Kinabalu, Sandakan, Tawau); Sarawak (Kuching, Miri, Sibu); Selangor (Petaling Jaya, Shah Alam, Klang, Subang Jaya); Terengganu (Kuala Terengganu); Kuala Lumpur; Putrajaya; Labuan.

These are **starting points**, not exhaustive coverage of every town, business or company in Malaysia.

## Workflow
1. Run city-focused research from public business directories or business website inputs.
2. Only retain emails actually published by a company or public directory, alongside the source and discovery date; do not treat guessed addresses as validated.
3. Merge CSV/Excel exports, normalize domains and deduplicate addresses.
4. Maintain a private do-not-contact CSV (do not commit any personal marketing-contact database into this public repository). Exclude opt-outs across **all** campaign lists.
5. Exclude failed addresses and verify relevance before any email.
6. Do not send mass unsolicited messages or attempt to bypass spam filters.

For location-based collection, use the separate fork: [radial-lead-scraper](https://github.com/victorgregory21-cell/radial-lead-scraper), which now includes `malaysia_scan.py` to run the same search type across multiple Malaysian cities. Import its resulting CSV here for company website enrichment and data cleaning.

## Opt-out protection
Keep opt-out addresses and campaign suppression files in private storage, outside this public repository. Load the do-not-contact CSV before exporting leads or sending any outreach. Never commit actual subscriber or recipient addresses.

No automated email sending is configured by this guide.
