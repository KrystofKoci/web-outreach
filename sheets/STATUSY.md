# Stavy leadu (sloupec `status` v listu `leads`)

Jeden lead = jeden řádek v listu `leads`. Sloupec `status` je jediný „řídicí“ údaj – každý workflow si vybírá řádky podle něj a po práci ho přepíše. Nikdy neměň `id` (Google Place ID, resp. `manual-…` / `form-…` / `wa-…` u ručně vložených).

**Kanály:** první kontakt je vždy jen **e-mail**. WhatsApp s klientem jen tehdy, když klient napíše první (na firemní WhatsApp číslo) nebo sám pošle číslo a o WhatsApp požádá (`whatsapp_opt_in=TRUE`). Nikdy cold WhatsApp. Žádné hovory ani schůzky – vše se dotahuje písemně.

## Stavový automat

```
                 01 lead finder
                       │
                       ▼
                     new ──────────────► blocked        (CR / BLOCKED_COUNTRIES / legal_regime=blocked)
                       │ 02 audit
                       ▼
                  processing
         ┌────────────┼──────────────────┬──────────────┐
         ▼            ▼                  ▼              ▼
 awaiting_approval  needs_email        skipped         error
 (má veřejný        (redesign, e-mail  (branch=skip,   (/process selhal,
  e-mail)            se nenašel)        nebo bez webu    viz notes)
                                        a bez e-mailu)
         │ 03 dávka 8/11/14 → schvalovací stránka (odkaz WhatsApp + e-mail)
   ┌─────┴────────┐
   ▼              ▼
approved       rejected
   │ 04 sekvence
   ▼
 sent_1 ──(+3 prac. dny)──► sent_2 ──(+4 prac. dny)──► sent_3 ──(14 dní ticho, neděle)──► no_response
   │                          │                          │
   └──────── odpověď e-mailem / WhatsApp / formulář / odhlášení / bounce (05, 07) ─────┐
                                                                                      ▼
   replied · interested · negotiating · lost · unsubscribed (+blocklist) · bounced (+blocklist) · do_not_contact
        │ objednávka → agent eskaluje → ty potvrdíš
        ▼
       won  ──► řádek v listu `deals` (MCP uzavrit_zakazku okamžitě, ruční přepis statusu do hodiny)
```

## Význam jednotlivých stavů

| status | kdo nastaví | co znamená | co se s ním děje dál |
|---|---|---|---|
| `new` | 01, MCP `hledej_firmy` | nalezeno přes Google Places, zatím bez auditu | 02 bere max. 8 řádků každých 20 min |
| `processing` | 02 | právě běží `/process` | přepíše se do 20 min; když zůstane > 2 h, je to chyba pipeline |
| `awaiting_approval` | 02 | náhled hotový, veřejný e-mail nalezený | 03 ho zařadí do nejbližší dávky (08/11/14 h) |
| `needs_email` | 02 | redesign, ale e-mail se nenašel | doplň `email` ručně a přepiš na `awaiting_approval`, jinak nic |
| `skipped` | 02 / 04 | web v pořádku, firma bez webu a bez e-mailu, nebo doména kontaktovaná < 90 dní | nic; po 180 dnech anonymizace |
| `blocked` | 01 / 02 / 04 | země nebo právní režim blokovaný | nikdy se neposílá |
| `error` | 02 | `/process` spadl (důvod v `notes`) | oprav příčinu a vrať na `new` |
| `approved` | schvalovací stránka (✅ / Schválit vše), MCP `schvalit` | smíš poslat 1. e-mail | 04 pošle v okně po–pá 08:30–11:30, 13:30–16:00 času leadu |
| `rejected` | schvalovací stránka (❌), MCP `zamitnout` | teď neoslovovat | po 180 dnech anonymizace |
| `do_not_contact` | MCP `nekontaktovat`, agent při stížnosti | nikdy nekontaktovat; e-mail/doména v `blocklist` | nic |
| `sent_1` / `sent_2` / `sent_3` | 04 | odeslán 1./2./3. e-mail | 04 hlídá další krok, 05 odpovědi |
| `no_response` | 06 (neděle) | po 3. e-mailu 14 dní ticho | uzavřeno; učení jako negativní výsledek |
| `replied` | 05 | dotaz / jiná odpověď | agent odpověděl nebo eskaloval (`next_action=owner`) |
| `interested` | 05 / 07 (formulář) | projevený zájem | agent odpovídá písemně; ty dotahuješ |
| `negotiating` | 05 | řeší se cena / rozsah | agent v mantinelech ceníku, objednávku eskaluje |
| `lost` | 05, ty | slušné ne | nic |
| `unsubscribed` | 05 / 07 | odhlášení nebo „NEMÁM ZÁJEM“ | e-mail i doména do `blocklist`, nikdy dál |
| `bounced` | 05 | nedoručitelné | e-mail do `blocklist` |
| `won` | MCP `uzavrit_zakazku`, ruční přepis | zakázka uzavřena | řádek v `deals`; vstupuje do učení |

## Pomocné sloupce

- `next_action` – `owner` = agent eskaloval, čeká na tebe (agent do vlákna nepíše, dokud to nesmažeš); prázdné = automatika běží.
- `manual_takeover` – `TRUE` jakmile v e-mailovém vlákně odpovíš sám; agent už nepíše.
- `auto_reply_count` – kolik odpovědí agent poslal (max 2 za lead, pak eskalace).
- `whatsapp` / `whatsapp_opt_in` – číslo klienta (E.164) a jestli WhatsApp sám inicioval / požádal o něj. Bez `TRUE` se na WhatsApp nikdy nepíše.
- `last_channel` – `email` / `whatsapp` / `form` – kudy přišla poslední zpráva.
- `custom_subject` – vlastní předmět 1. e-mailu (✏️ na schvalovací stránce). `custom_intro` – vlastní úvodní odstavec (pište přímo do listu).
- `subject_variant` – A/B/C (viz `emails/*/subjects.md`), přiřadí se při zařazení do dávky.
- `batch_id` / `notified_at` – do které dávky lead patřil a kdy.
- `reasons` – důvody auditu v jazyce leadu (`{{reason_1}}` v e-mailu), `reasons_cs` – česky pro tebe.

## Ostatní listy

- `queue` – co hledat (země, město, kategorie, jazyk, trh, `enabled`, `weight`).
- `weights` – výstup nedělního `/learn` (`segment`, `weight`, `reply_rate`, `win_rate`, `n`).
- `deals` – uzavřené zakázky (hlavička `deals.csv`); `price_final` doplň, pokud se liší.
- `blocklist` – `value` (e-mail nebo doména), `type`, `reason`, `added_at`, `lead_id`. Kontroluje se před každým odesláním.
