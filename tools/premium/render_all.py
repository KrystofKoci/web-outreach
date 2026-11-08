import sys, json, shutil
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from pathlib import Path
from pipeline.models import Lead
from pipeline.config import get_settings
from pipeline import premium
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/prev')
mode = sys.argv[2] if len(sys.argv) > 2 else 'full'
if OUT.exists(): shutil.rmtree(OUT)
s = get_settings(); s.form_webhook_url = 'https://n8n.krystofkoci.com/webhook/form'; s.owner_whatsapp = '+420607778711'
HRS = ["Monday: 8:00 AM – 5:00 PM", "Tuesday: 8:00 AM – 5:00 PM", "Wednesday: 8:00 AM – 5:00 PM", "Thursday: 8:00 AM – 6:00 PM",
       "Friday: 8:00 AM – 4:00 PM", "Saturday: 9:00 AM – 12:00 PM", "Sunday: Closed"]
NAMES = {'autoservis': ('Autoservis Novák s.r.o.', 'Car Repair Smith & Sons'), 'elektrikar': ('Elektro Dvořák', 'Bright Spark Electrical'),
         'opravar': ('Opravy spotřebičů Malý', 'Fix-It Appliance Repair'), 'kadernictvi': ('Kadeřnictví Jana', 'Studio Grace Hair'),
         'restaurace': ('Restaurace U Lípy', 'The Linden Kitchen'), 'kvetinarstvi': ('Květinářství Fialka', 'Violet Flowers'),
         'barber': ('Barbershop Brno', 'Northside Barbers')}
for niche, ids in premium.TEMPLATES_BY_NICHE.items():
    for tid in ids:
        for lang in ('cs', 'en'):
            nm = NAMES[niche][0 if lang == 'cs' else 1]
            kw = dict(id=f'test-{tid}-{lang}', name=nm, country='CZ' if lang == 'cs' else 'US', lang=lang, market='cz' if lang == 'cs' else 'en',
                      city='Brno' if lang == 'cs' else 'Tulsa')
            if mode == 'full':
                kw.update(address='Křenová 12, 602 00 Brno' if lang == 'cs' else '120 Main St, Tulsa, OK 74103', phone='777 123 456' if lang == 'cs' else '(918) 555-0142',
                          phone_intl='+420777123456' if lang == 'cs' else '+19185550142', rating=4.8, rating_count=87, opening_hours=HRS,
                          maps_url='https://maps.google.com/?cid=1', website='https://example.com')
            lead = Lead(**kw)
            slug = f'{tid}-{lang}'
            d = OUT / slug; d.mkdir(parents=True)
            premium.install_assets(OUT, tid)
            html = premium.render(lead, tid, s, slug=slug, best_email='info@example.com' if mode == 'full' else '', preview_url='')
            (d / 'index.html').write_text(html, encoding='utf-8')
print('ok', OUT)
