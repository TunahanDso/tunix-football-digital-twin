# Competition seed provenance

The competition JSON files are source-neutral domain data. Provider-specific names and IDs are resolved separately; these files intentionally keep stable TUNIX keys and canonical names.

## `tr_super_lig_2024_25.json`

Authoritative references used for the first Süper Lig seed:

- Türkiye Futbol Federasyonu — 2024-2025 Trendyol Süper Lig fixture and table: https://www.tff.org/Default.aspx?pageId=1730
- Türkiye Futbol Federasyonu — 2024-2025 professional league statutes announcement: https://www.tff.org/default.aspx?ftxtID=44968&pageID=687
- Türkiye Futbol Federasyonu — 2024-2025 Süper Lig statute: https://www.tff.org/Resources/TFF/Documents/STATULER/2024-2025/2024-2025-Sezonu-Trendyol-Super-Lig-Musabakalari-Statusu.pdf
- Türkiye Futbol Federasyonu — 2023-2024 final registration decision, including promotion of Eyüpspor, Göztepe and Bodrum FK: https://www.tff.org/default.aspx?ftxtID=44507&pageID=204
- Türkiye Futbol Federasyonu — 2024-2025 final registration decision, including the four relegated clubs: https://www.tff.org/Default.aspx?ftxtId=47764&pageId=200

## Historical fixture revision sample

`data/fixtures/tr_super_lig_2024_25_history_sample.json` demonstrates that the same fixture can have multiple historically valid states instead of rewriting the past.

- TFF — 16 August 2024 week-three postponement announcement: https://www.tff.org/default.aspx?ftxtID=45077&pageID=687
- TFF — 13 February 2025 PFDK decision for Galatasaray–Adana Demirspor, including the 3-0 awarded result and points sanction: https://www.tff.org/default.aspx?ftxtID=46746&pageID=246
- TFF — registered match detail for Galatasaray–Adana Demirspor: https://www.tff.org/Default.aspx?macId=264193&pageID=29

Dates in source-neutral fixture files are timezone-aware and are normalized to UTC by the ingestion contract when used by temporal model code.
