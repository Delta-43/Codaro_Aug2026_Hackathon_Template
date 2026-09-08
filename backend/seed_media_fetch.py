"""Fetch royalty-free imagery for the funeral-home demo seed.

Every image is a Wikimedia Commons file, addressed by its direct
``upload.wikimedia.org`` URL: stable, no API key, no hotlink policy, and a
licence that permits reuse with attribution (written to
``frontend/public/media/CREDITS.md`` alongside the files).

This module is **entirely optional infrastructure**. Nothing in the seed path
depends on it succeeding:

* Files already on disk are never re-downloaded, so re-running is cheap and
  offline-safe once the cache is warm.
* Every fetch is wrapped individually — a 404, a DNS failure or a dead CDN is
  logged and skipped, never raised. ``ensure_media`` cannot fail a reseed.
* A slug with no file on disk simply makes ``seed_media`` return ``None``, and
  ``seed.py`` falls back to its generated SVG gradient.

Run it directly (``python3 backend/seed_media_fetch.py``) or via ``make
fetchmedia``. Seeding calls it only when ``SEED_FETCH_MEDIA=1`` is set.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# `backend/seed_media_fetch.py` -> repo root -> frontend/public/media
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "media"

# Wikimedia rejects urllib's default User-Agent outright (403), so identify.
_USER_AGENT = "CodaroSeedMedia/1.0 (booking-engine demo seed; +https://example.com/codaro)"
_TIMEOUT = 30
# Wikimedia throttles bursts with a 429. Pace the requests and back off rather
# than hammering — a rate-limited run leaves gaps, and gaps become gradients.
_DELAY = 1.2
_RETRIES = 4

# slug (relative path under the media root, no extension) -> direct image URL.
# Keys must match the slugs in `seed_media.py`; the file lands at
# `<root>/<slug>.jpg`.
SOURCES: dict[str, str] = {
    'arrangements/adjacent-plot': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/White_and_golden_graves_in_a_Buddhist_cemetery_at_sunrise_in_Vang_Vieng%2C_Laos.jpg/1920px-White_and_golden_graves_in_a_Buddhist_cemetery_at_sunrise_in_Vang_Vieng%2C_Laos.jpg',
    'arrangements/burial': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Cimetiere_americain_Colleville-sur-Mer.jpg/1920px-Cimetiere_americain_Colleville-sur-Mer.jpg',
    'arrangements/chapel-a': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Brickendon_Chapel_of_the_Holy_Cross_and_St_Alban_north-west_nave_pews_Hertfordshire_England_01.jpg/1920px-Brickendon_Chapel_of_the_Holy_Cross_and_St_Alban_north-west_nave_pews_Hertfordshire_England_01.jpg',
    'arrangements/chapel-b': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Votive_candles_at_the_Huron_University_College_Chapel_in_London%2C_Ontario.jpg/1920px-Votive_candles_at_the_Huron_University_College_Chapel_in_London%2C_Ontario.jpg',
    'arrangements/cremation': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/La_Funeraria_Paz_Chapels_and_Crematorium_furnace_green20.jpg/1920px-La_Funeraria_Paz_Chapels_and_Crematorium_furnace_green20.jpg',
    'arrangements/cryo-vault': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Cryogenic_gas_storage_tanks_at_the_Max_Planck_Institute_for_Plasma_Physics_in_Greifswald.jpg/1920px-Cryogenic_gas_storage_tanks_at_the_Max_Planck_Institute_for_Plasma_Physics_in_Greifswald.jpg',
    'arrangements/cryogenic-suspension': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/%D0%97%D0%BD%D0%B0%D0%BA%D0%BE%D0%BC%D1%81%D1%82%D0%B2%D0%B0_%D1%81_%D0%B6%D0%B8%D0%B4%D0%BA%D0%B8%D0%BC_%D0%B0%D0%B7%D0%BE%D1%82%D0%B0%D0%BC_%D1%84%D0%BE%D1%82%D0%BE_%E2%84%96_7_%D0%B8%D0%B7_7.jpg/1920px-%D0%97%D0%BD%D0%B0%D0%BA%D0%BE%D0%BC%D1%81%D1%82%D0%B2%D0%B0_%D1%81_%D0%B6%D0%B8%D0%B4%D0%BA%D0%B8%D0%BC_%D0%B0%D0%B7%D0%BE%D1%82%D0%B0%D0%BC_%D1%84%D0%BE%D1%82%D0%BE_%E2%84%96_7_%D0%B8%D0%B7_7.jpg',
    'arrangements/direct-committal': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/A_simple_rock_is_used_as_a_headstone_at_Pine_Hill_Cemetery_in_St._James%2C_Missouri_%288916c749-480b-4566-af37-7a29c78147f4%29.JPG/1920px-A_simple_rock_is_used_as_a_headstone_at_Pine_Hill_Cemetery_in_St._James%2C_Missouri_%288916c749-480b-4566-af37-7a29c78147f4%29.JPG',
    'arrangements/discreet-arrangement': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Memento_Mori_-_Closed_casket_Wellcome_L0043757.jpg/1920px-Memento_Mori_-_Closed_casket_Wellcome_L0043757.jpg',
    'arrangements/hearse-horse-drawn': 'https://upload.wikimedia.org/wikipedia/commons/f/fb/Horse-drawn_hearse%2C_Lowtown%2C_Pudsey_-_geograph.org.uk_-_6426051.jpg',
    'arrangements/hearse-mercedes': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Mercedes-Benz_Hearse%2C_rear.jpg/1920px-Mercedes-Benz_Hearse%2C_rear.jpg',
    'arrangements/hearse-rolls-royce': 'https://upload.wikimedia.org/wikipedia/commons/0/03/212_Hearse_%26_Limo_NFE.jpg',
    'arrangements/launch-pad': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Space_Shuttle_Columbia_launching.jpg/1920px-Space_Shuttle_Columbia_launching.jpg',
    'arrangements/memorial-gathering': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/db/Flowers_and_candles_at_the_monument_to_Josip_Jovi%C4%87.jpg/1920px-Flowers_and_candles_at_the_monument_to_Josip_Jovi%C4%87.jpg',
    'arrangements/nocturnal-aftercare': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/030_All_Saints_Day_celebration_in_Poland_-_grave_candles_in_the_evening.jpg/1920px-030_All_Saints_Day_celebration_in_Poland_-_grave_candles_in_the_evening.jpg',
    'arrangements/orbital-committal': 'https://upload.wikimedia.org/wikipedia/commons/2/2d/First_NASA_ISINGLASS_rocket_launch.jpg',
    'arrangements/pre-need-arrangement': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Office_desk_with_papers_-_DPLA_-_bacc10bd7825152341818a63e9628905.jpg/1920px-Office_desk_with_papers_-_DPLA_-_bacc10bd7825152341818a63e9628905.jpg',
    'arrangements/preparation-suite': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Mortuary_room_.jpg/1920px-Mortuary_room_.jpg',
    'arrangements/retort-1': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/La_Funeraria_Paz_Chapels_and_Crematorium_furnaces19.jpg/1920px-La_Funeraria_Paz_Chapels_and_Crematorium_furnaces19.jpg',
    'arrangements/retort-2': 'https://upload.wikimedia.org/wikipedia/commons/5/5d/TT_CMZ-AF-GT_E_2-1_14_5_-_Forno_cremat%C3%B3rio.jpg',
    'arrangements/traditional-funeral': 'https://upload.wikimedia.org/wikipedia/commons/3/3b/Tony_O%27Reilly_funeral_at_Donnybrook_coffin_afterwards.jpg',
    'avatars/agnieszka-nowak': 'https://upload.wikimedia.org/wikipedia/commons/8/87/Unidentified_young_woman%2C_formal_portrait_%287045670531%29.jpg',
    'avatars/andrzej-stepien': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Old_man_with_hearing_aid._%28Unsplash%29.jpg/1920px-Old_man_with_hearing_aid._%28Unsplash%29.jpg',
    'avatars/beata-szymanska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Smiling_woman_%28Unsplash%29.jpg/1920px-Smiling_woman_%28Unsplash%29.jpg',
    'avatars/dorota-sadowska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Closed_eye_smile_%28Unsplash%29.jpg/1920px-Closed_eye_smile_%28Unsplash%29.jpg',
    'avatars/elzbieta-kaminska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Elderly_Gambian_woman_face_portrait.jpg/1920px-Elderly_Gambian_woman_face_portrait.jpg',
    'avatars/ewa-duda': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Woman_in_glasses_smiling_%28Unsplash%29.jpg/1920px-Woman_in_glasses_smiling_%28Unsplash%29.jpg',
    'avatars/halina-baran': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Girl_close-up_face_portrait_%2849749906893%29.jpg/1920px-Girl_close-up_face_portrait_%2849749906893%29.jpg',
    'avatars/henryk-walczak': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Chapard._Reproduction_after_watercolour_by_%28B._Y.%29._Wellcome_V0001064.jpg/1920px-Chapard._Reproduction_after_watercolour_by_%28B._Y.%29._Wellcome_V0001064.jpg',
    'avatars/irena-wojcik': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Head_Scarf_%28Unsplash%29.jpg/1920px-Head_Scarf_%28Unsplash%29.jpg',
    'avatars/jan-dabrowski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/Bearded_man_smoking_pipe-3013924.jpg/1920px-Bearded_man_smoking_pipe-3013924.jpg',
    'avatars/katarzyna-lewandowska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Portrait_%28Unsplash%29.jpg/1920px-Portrait_%28Unsplash%29.jpg',
    'avatars/krzysztof-malinowski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Gray-haired_man_portrait_%28Unsplash%29.jpg/1920px-Gray-haired_man_portrait_%28Unsplash%29.jpg',
    'avatars/lukas-behrend': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Face_portrait_%28Unsplash%29.jpg/1920px-Face_portrait_%28Unsplash%29.jpg',
    'avatars/mara-lindqvist': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Vermeer-Portrait_of_a_Young_Woman.jpg/1920px-Vermeer-Portrait_of_a_Young_Woman.jpg',
    'avatars/marek-kowalczyk': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Monochrome_bearded_man_%28Unsplash%29.jpg/1920px-Monochrome_bearded_man_%28Unsplash%29.jpg',
    'avatars/michal-sikora': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Man_with_wrinkles_and_cap_%28Unsplash%29.jpg/1920px-Man_with_wrinkles_and_cap_%28Unsplash%29.jpg',
    'avatars/natalia-krawczyk': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/94/Smiling_Over_Her_Shoulder_%28Unsplash%29.jpg/1920px-Smiling_Over_Her_Shoulder_%28Unsplash%29.jpg',
    'avatars/pawel-gorski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Curly_hair_and_freckles_man_%28Unsplash%29.jpg/1920px-Curly_hair_and_freckles_man_%28Unsplash%29.jpg',
    'avatars/piotr-zielinski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Portrait_of_a_man_%28Unsplash%29.jpg/1920px-Portrait_of_a_man_%28Unsplash%29.jpg',
    'avatars/robert-mazur': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Man_with_a_white_beard_and_glasses%2C_by_Angelina_Litvin%2C_2015-10-05_%28Unsplash%29.jpg/1920px-Man_with_a_white_beard_and_glasses%2C_by_Angelina_Litvin%2C_2015-10-05_%28Unsplash%29.jpg',
    'avatars/tomasz-wisniewski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Portrait_of_a_Man%2C_Said_to_be_Christopher_Columbus.jpg/1920px-Portrait_of_a_Man%2C_Said_to_be_Christopher_Columbus.jpg',
    'avatars/zofia-adamska': 'https://upload.wikimedia.org/wikipedia/commons/d/d5/A_very_beautiful_old_lady_II_%28443738371%29.jpg',
    'homes/cichy-dom': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Green-Wood_Cemetery_gate_%2853784p%29_cropped.jpg/1920px-Green-Wood_Cemetery_gate_%2853784p%29_cropped.jpg',
    'homes/cichy-dom-cover': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Skogskyrkogarden-night-2007-11-03.JPG/1920px-Skogskyrkogarden-night-2007-11-03.JPG',
    'homes/dom-zaloby-bursztyn': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Funchal_Chapel_British_Cemetery_Interior.JPG/1920px-Funchal_Chapel_British_Cemetery_Interior.JPG',
    'homes/dom-zaloby-bursztyn-cover': 'https://upload.wikimedia.org/wikipedia/commons/8/8d/Baltic_sea-coast%2C_grey_dune_-_panoramio.jpg',
    'homes/kaplica-lipowa': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Royal_crematorium_of_King_Rama_IX_at_night.jpg/1920px-Royal_crematorium_of_King_Rama_IX_at_night.jpg',
    'homes/kaplica-lipowa-cover': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/City_of_London_Cemetery_and_Crematorium_Anglican_Church_chapel_west_twin_light_window_dappled_light_1.jpg/1920px-City_of_London_Cemetery_and_Crematorium_Anglican_Church_chapel_west_twin_light_window_dappled_light_1.jpg',
    'homes/odra-pamiec': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Rainey_Funeral_Home_Building.jpg/1920px-Rainey_Funeral_Home_Building.jpg',
    'homes/odra-pamiec-cover': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Rows_of_Gravestones_at_The_Normandy_American_Cemetery_and_Memorial.jpg/1920px-Rows_of_Gravestones_at_The_Normandy_American_Cemetery_and_Memorial.jpg',
    'homes/ostatnia-granica': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Liquid_Nitrogen_Tank.JPG/1920px-Liquid_Nitrogen_Tank.JPG',
    'homes/ostatnia-granica-cover': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/NASA%E2%80%99s_Evolved_SLS_Block_1B_Crew_Rocket_-_Night_Launch_%28B1B_Crew_Night_Launch%29.jpg/1920px-NASA%E2%80%99s_Evolved_SLS_Block_1B_Crew_Rocket_-_Night_Launch_%28B1B_Crew_Night_Launch%29.jpg',
    'homes/wieczny-spokoj': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Altar_in_chapel_at_Greenwich_Hospital%2C_London.jpg/1920px-Altar_in_chapel_at_Greenwich_Hospital%2C_London.jpg',
    'homes/wieczny-spokoj-cover': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Lipov%C3%A1_alej%2C_Ol%C5%A1ansk%C3%A9_h%C5%99bitovy_l.%2C_Ol%C5%A1any%2C_Praha_3_-_%C5%BDi%C5%BEkov.jpg/1920px-Lipov%C3%A1_alej%2C_Ol%C5%A1ansk%C3%A9_h%C5%99bitovy_l.%2C_Ol%C5%A1any%2C_Praha_3_-_%C5%BDi%C5%BEkov.jpg',
}

# Attribution per slug, rendered into CREDITS.md next to the files.
CREDITS: dict[str, dict[str, str]] = {
    'arrangements/adjacent-plot': {
        'title': 'White and golden graves in a Buddhist cemetery at sunrise in Vang Vieng, Laos.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:White_and_golden_graves_in_a_Buddhist_cemetery_at_sunrise_in_Vang_Vieng,_Laos.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Basile Morin',
    },
    'arrangements/burial': {
        'title': 'Cimetiere americain Colleville-sur-Mer.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Cimetiere_americain_Colleville-sur-Mer.jpg',
        'license': 'CC BY-SA 3.0',
        'author': 'Myrabella',
    },
    'arrangements/chapel-a': {
        'title': 'Brickendon Chapel of the Holy Cross and St Alban north-west nave pews Hertfordshire England 01.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Brickendon_Chapel_of_the_Holy_Cross_and_St_Alban_north-west_nave_pews_Hertfordshire_England_01.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Acabashi',
    },
    'arrangements/chapel-b': {
        'title': 'Votive candles at the Huron University College Chapel in London, Ontario.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Votive_candles_at_the_Huron_University_College_Chapel_in_London,_Ontario.jpg',
        'license': 'CC BY 4.0',
        'author': 'Gogerr',
    },
    'arrangements/cremation': {
        'title': 'La Funeraria Paz Chapels and Crematorium furnace green20.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:La_Funeraria_Paz_Chapels_and_Crematorium_furnace_green20.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'see file page',
    },
    'arrangements/cryo-vault': {
        'title': 'Cryogenic gas storage tanks at the Max Planck Institute for Plasma Physics in Greifswald.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Cryogenic_gas_storage_tanks_at_the_Max_Planck_Institute_for_Plasma_Physics_in_Greifswald.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Siarhei Besarab',
    },
    'arrangements/cryogenic-suspension': {
        'title': 'Знакомства с жидким азотам фото № 7 из 7.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:%D0%97%D0%BD%D0%B0%D0%BA%D0%BE%D0%BC%D1%81%D1%82%D0%B2%D0%B0_%D1%81_%D0%B6%D0%B8%D0%B4%D0%BA%D0%B8%D0%BC_%D0%B0%D0%B7%D0%BE%D1%82%D0%B0%D0%BC_%D1%84%D0%BE%D1%82%D0%BE_%E2%84%96_7_%D0%B8%D0%B7_7.jpg',
        'license': 'CC BY 4.0',
        'author': 'Rodion Plotnikov',
    },
    'arrangements/direct-committal': {
        'title': 'A simple rock is used as a headstone at Pine Hill Cemetery in St. James, Missouri (8916c749-480b-4566-af37-7a29c78147f4).JPG',
        'page': 'https://commons.wikimedia.org/wiki/File:A_simple_rock_is_used_as_a_headstone_at_Pine_Hill_Cemetery_in_St._James,_Missouri_(8916c749-480b-4566-af37-7a29c78147f4).JPG',
        'license': 'Public domain',
        'author': 'National Trails Office (US National Park Service)',
    },
    'arrangements/discreet-arrangement': {
        'title': 'Memento Mori - Closed casket Wellcome L0043757.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Memento_Mori_-_Closed_casket_Wellcome_L0043757.jpg',
        'license': 'CC BY 4.0',
        'author': 'see file page',
    },
    'arrangements/hearse-horse-drawn': {
        'title': 'Horse-drawn hearse, Lowtown, Pudsey - geograph.org.uk - 6426051.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Horse-drawn_hearse,_Lowtown,_Pudsey_-_geograph.org.uk_-_6426051.jpg',
        'license': 'CC BY-SA 2.0',
        'author': 'Stephen Craven',
    },
    'arrangements/hearse-mercedes': {
        'title': 'Mercedes-Benz Hearse, rear.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Mercedes-Benz_Hearse,_rear.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'User:Mattes',
    },
    'arrangements/hearse-rolls-royce': {
        'title': '212 Hearse & Limo NFE.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:212_Hearse_%26_Limo_NFE.jpg',
        'license': 'CC BY-SA 3.0',
        'author': 'Lavinia.stana',
    },
    'arrangements/launch-pad': {
        'title': 'Space Shuttle Columbia launching.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Space_Shuttle_Columbia_launching.jpg',
        'license': 'Public domain',
        'author': 'NASA',
    },
    'arrangements/memorial-gathering': {
        'title': 'Flowers and candles at the monument to Josip Jović.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Flowers_and_candles_at_the_monument_to_Josip_Jovi%C4%87.jpg',
        'license': 'CC BY 2.0',
        'author': 'Donald Judge from England',
    },
    'arrangements/nocturnal-aftercare': {
        'title': '030 All Saints Day celebration in Poland - grave candles in the evening.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:030_All_Saints_Day_celebration_in_Poland_-_grave_candles_in_the_evening.jpg',
        'license': 'CC BY 3.0',
        'author': 'Marek Ślusarczyk (Tupungato) Photo portfolio',
    },
    'arrangements/orbital-committal': {
        'title': 'First NASA ISINGLASS rocket launch.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:First_NASA_ISINGLASS_rocket_launch.jpg',
        'license': 'Public domain',
        'author': 'NASA',
    },
    'arrangements/pre-need-arrangement': {
        'title': 'Office desk with papers - DPLA - bacc10bd7825152341818a63e9628905.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Office_desk_with_papers_-_DPLA_-_bacc10bd7825152341818a63e9628905.jpg',
        'license': 'Public domain',
        'author': 'David E. Lucas',
    },
    'arrangements/preparation-suite': {
        'title': 'Mortuary room .jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Mortuary_room_.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Adbh266',
    },
    'arrangements/retort-1': {
        'title': 'La Funeraria Paz Chapels and Crematorium furnaces19.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:La_Funeraria_Paz_Chapels_and_Crematorium_furnaces19.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Judgefloro',
    },
    'arrangements/retort-2': {
        'title': 'TT CMZ-AF-GT E 2-1 14 5 - Forno crematório.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:TT_CMZ-AF-GT_E_2-1_14_5_-_Forno_cremat%C3%B3rio.jpg',
        'license': 'Public domain',
        'author': 'Companhia de Moçambique',
    },
    'arrangements/traditional-funeral': {
        'title': "Tony O'Reilly funeral at Donnybrook coffin afterwards.jpg",
        'page': 'https://commons.wikimedia.org/wiki/File:Tony_O%27Reilly_funeral_at_Donnybrook_coffin_afterwards.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Rcarter74',
    },
    'avatars/agnieszka-nowak': {
        'title': 'Unidentified young woman, formal portrait (7045670531).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Unidentified_young_woman,_formal_portrait_(7045670531).jpg',
        'license': 'No restrictions',
        'author': 'Mennonite Church USA Archives',
    },
    'avatars/andrzej-stepien': {
        'title': 'Old man with hearing aid. (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Old_man_with_hearing_aid._(Unsplash).jpg',
        'license': 'CC0',
        'author': 'JD Mason',
    },
    'avatars/beata-szymanska': {
        'title': 'Smiling woman (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Smiling_woman_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Allef Vinicius',
    },
    'avatars/dorota-sadowska': {
        'title': 'Closed eye smile (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Closed_eye_smile_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Marcelo Matarazzo',
    },
    'avatars/elzbieta-kaminska': {
        'title': 'Elderly Gambian woman face portrait.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Elderly_Gambian_woman_face_portrait.jpg',
        'license': 'CC BY-SA 2.0',
        'author': 'Ferdinand Reus',
    },
    'avatars/ewa-duda': {
        'title': 'Woman in glasses smiling (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Woman_in_glasses_smiling_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Ehimetalor Unuabona',
    },
    'avatars/halina-baran': {
        'title': 'Girl close-up face portrait (49749906893).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Girl_close-up_face_portrait_(49749906893).jpg',
        'license': 'CC BY 2.0',
        'author': 'Pedro Ribeiro Simões',
    },
    'avatars/henryk-walczak': {
        'title': 'Chapard. Reproduction after watercolour by (B. Y.). Wellcome V0001064.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Chapard._Reproduction_after_watercolour_by_(B._Y.)._Wellcome_V0001064.jpg',
        'license': 'CC BY 4.0',
        'author': 'Antoine Bisetzky (1817-1892)',
    },
    'avatars/irena-wojcik': {
        'title': 'Head Scarf (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Head_Scarf_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Roksolana Zasiadko',
    },
    'avatars/jan-dabrowski': {
        'title': 'Bearded man smoking pipe-3013924.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Bearded_man_smoking_pipe-3013924.jpg',
        'license': 'CC0',
        'author': 'ThuyHaBich',
    },
    'avatars/katarzyna-lewandowska': {
        'title': 'Portrait (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Portrait_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Alesia Kazantceva',
    },
    'avatars/krzysztof-malinowski': {
        'title': 'Gray-haired man portrait (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Gray-haired_man_portrait_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Foto Sushi',
    },
    'avatars/lukas-behrend': {
        'title': 'Face portrait (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Face_portrait_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'William Stitt',
    },
    'avatars/mara-lindqvist': {
        'title': 'Vermeer-Portrait of a Young Woman.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Vermeer-Portrait_of_a_Young_Woman.jpg',
        'license': 'Public domain',
        'author': 'Johannes Vermeer',
    },
    'avatars/marek-kowalczyk': {
        'title': 'Monochrome bearded man (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Monochrome_bearded_man_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Seth Doyle',
    },
    'avatars/michal-sikora': {
        'title': 'Man with wrinkles and cap (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Man_with_wrinkles_and_cap_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Kahar Saidyhalam',
    },
    'avatars/natalia-krawczyk': {
        'title': 'Smiling Over Her Shoulder (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Smiling_Over_Her_Shoulder_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Clem Onojeghuo',
    },
    'avatars/pawel-gorski': {
        'title': 'Curly hair and freckles man (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Curly_hair_and_freckles_man_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Jeremy Bishop',
    },
    'avatars/piotr-zielinski': {
        'title': 'Portrait of a man (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Portrait_of_a_man_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'William Stitt',
    },
    'avatars/robert-mazur': {
        'title': 'Man with a white beard and glasses, by Angelina Litvin, 2015-10-05 (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Man_with_a_white_beard_and_glasses,_by_Angelina_Litvin,_2015-10-05_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Angelina Litvin',
    },
    'avatars/tomasz-wisniewski': {
        'title': 'Portrait of a Man, Said to be Christopher Columbus.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Portrait_of_a_Man,_Said_to_be_Christopher_Columbus.jpg',
        'license': 'Public domain',
        'author': 'Sebastiano del Piombo',
    },
    'avatars/zofia-adamska': {
        'title': 'A very beautiful old lady II (443738371).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:A_very_beautiful_old_lady_II_(443738371).jpg',
        'license': 'CC BY 2.0',
        'author': 'Pedro Ribeiro Simões',
    },
    'homes/cichy-dom': {
        'title': 'Green-Wood Cemetery gate (53784p) cropped.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Green-Wood_Cemetery_gate_(53784p)_cropped.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Rhododendrites',
    },
    'homes/cichy-dom-cover': {
        'title': 'Skogskyrkogarden-night-2007-11-03.JPG',
        'page': 'https://commons.wikimedia.org/wiki/File:Skogskyrkogarden-night-2007-11-03.JPG',
        'license': 'CC BY-SA 3.0',
        'author': 'BloodIce',
    },
    'homes/dom-zaloby-bursztyn': {
        'title': 'Funchal Chapel British Cemetery Interior.JPG',
        'page': 'https://commons.wikimedia.org/wiki/File:Funchal_Chapel_British_Cemetery_Interior.JPG',
        'license': 'CC BY-SA 4.0',
        'author': 'TeWeBs',
    },
    'homes/dom-zaloby-bursztyn-cover': {
        'title': 'Baltic sea-coast, grey dune - panoramio.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Baltic_sea-coast,_grey_dune_-_panoramio.jpg',
        'license': 'CC BY-SA 3.0',
        'author': 'Laima Gūtmane (simka…',
    },
    'homes/kaplica-lipowa': {
        'title': 'Royal crematorium of King Rama IX at night.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Royal_crematorium_of_King_Rama_IX_at_night.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'This Photo was taken by Supanut Arunoprayote. Feel free to use any of my images, but please mention me as the author and',
    },
    'homes/kaplica-lipowa-cover': {
        'title': 'City of London Cemetery and Crematorium Anglican Church chapel west twin light window dappled light 1.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:City_of_London_Cemetery_and_Crematorium_Anglican_Church_chapel_west_twin_light_window_dappled_light_1.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Acabashi',
    },
    'homes/odra-pamiec': {
        'title': 'Rainey Funeral Home Building.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Rainey_Funeral_Home_Building.jpg',
        'license': 'CC BY 4.0',
        'author': 'Larry D. Moore',
    },
    'homes/odra-pamiec-cover': {
        'title': 'Rows of Gravestones at The Normandy American Cemetery and Memorial.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Rows_of_Gravestones_at_The_Normandy_American_Cemetery_and_Memorial.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Matthew Eaton',
    },
    'homes/ostatnia-granica': {
        'title': 'Liquid Nitrogen Tank.JPG',
        'page': 'https://commons.wikimedia.org/wiki/File:Liquid_Nitrogen_Tank.JPG',
        'license': 'CC BY-SA 3.0',
        'author': 'Toby Hudson',
    },
    'homes/ostatnia-granica-cover': {
        'title': 'NASA’s Evolved SLS Block 1B Crew Rocket - Night Launch (B1B Crew Night Launch).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:NASA%E2%80%99s_Evolved_SLS_Block_1B_Crew_Rocket_-_Night_Launch_(B1B_Crew_Night_Launch).jpg',
        'license': 'Public domain',
        'author': 'NASA Marshall Space Flight Center / Terry White/SLS',
    },
    'homes/wieczny-spokoj': {
        'title': 'Altar in chapel at Greenwich Hospital, London.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Altar_in_chapel_at_Greenwich_Hospital,_London.jpg',
        'license': 'CC BY-SA 3.0',
        'author': 'Daniel Case',
    },
    'homes/wieczny-spokoj-cover': {
        'title': 'Lipová alej, Olšanské hřbitovy l., Olšany, Praha 3 - Žižkov.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Lipov%C3%A1_alej,_Ol%C5%A1ansk%C3%A9_h%C5%99bitovy_l.,_Ol%C5%A1any,_Praha_3_-_%C5%BDi%C5%BEkov.jpg',
        'license': 'CC BY-SA 4.0',
        'author': 'Fry72',
    },
}

_SUBDIRS = ("avatars", "homes", "arrangements")


def _dest(root: Path, slug: str) -> Path:
    return root / f"{slug}.jpg"


def _looks_like_image(blob: bytes) -> bool:
    """Reject HTML error pages that arrive with a 200."""
    return blob.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"RIFF"))


def _fetch_one(url: str, dest: Path) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    blob = b""
    for attempt in range(_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                blob = resp.read()
            break
        except urllib.error.HTTPError as exc:
            # 429/503 are transient throttling, not a dead URL — back off.
            if exc.code not in (429, 503) or attempt == _RETRIES - 1:
                raise
            time.sleep(_DELAY * (2 ** attempt) + 2)
    if not blob:
        return False, "empty response"
    if not _looks_like_image(blob):
        return False, "not an image (probably an error page)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(blob)
    tmp.replace(dest)  # atomic-ish: a half-written file never looks cached
    return True, f"{len(blob) // 1024} KiB"


def ensure_media(root: Path | None = None) -> dict:
    """Download any missing demo image into `root`. Never raises.

    Returns a summary dict: ``{"root", "downloaded", "skipped", "failed",
    "bytes", "misses"}``. Callers may log it; nothing should branch on it.
    """
    summary: dict = {
        "root": None, "downloaded": 0, "skipped": 0, "failed": 0,
        "bytes": 0, "misses": [],
    }
    try:
        root = Path(root) if root is not None else DEFAULT_ROOT
        summary["root"] = str(root)
        for sub in _SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # unwritable path, read-only FS, ...
        logger.warning("seed media: cannot prepare %s (%s) - skipping", root, exc)
        summary["failed"] = len(SOURCES)
        return summary

    for slug, url in SOURCES.items():
        dest = _dest(root, slug)
        try:
            if dest.exists() and dest.stat().st_size > 0:
                summary["skipped"] += 1
                summary["bytes"] += dest.stat().st_size
                continue
            time.sleep(_DELAY)
            ok, note = _fetch_one(url, dest)
            if ok:
                summary["downloaded"] += 1
                summary["bytes"] += dest.stat().st_size
                logger.debug("seed media: %s <- %s (%s)", slug, url, note)
            else:
                summary["failed"] += 1
                summary["misses"].append(f"{slug}: {note}")
        except Exception as exc:  # HTTPError, URLError, socket timeout, OSError
            summary["failed"] += 1
            summary["misses"].append(f"{slug}: {type(exc).__name__}: {exc}")
            try:
                dest.with_suffix(".part").unlink(missing_ok=True)
            except Exception:
                pass

    try:
        write_credits(root)
    except Exception as exc:
        logger.debug("seed media: could not write CREDITS.md (%s)", exc)

    if summary["misses"]:
        logger.info(
            "seed media: %d missing, falling back to generated gradients: %s",
            len(summary["misses"]), "; ".join(summary["misses"][:5]),
        )
    return summary


def maybe_ensure_media(root: Path | None = None) -> dict | None:
    """`ensure_media` gated on ``SEED_FETCH_MEDIA=1``. Safe to call from seeding."""
    if os.getenv("SEED_FETCH_MEDIA", "").strip() not in ("1", "true", "yes", "on"):
        return None
    try:
        return ensure_media(root)
    except Exception as exc:  # belt and braces - a reseed must never die here
        logger.warning("seed media: fetch skipped (%s)", exc)
        return None


def write_credits(root: Path | None = None) -> Path:
    """Write per-file attribution + licence for whatever actually landed."""
    root = Path(root) if root is not None else DEFAULT_ROOT
    lines = [
        "# Media credits",
        "",
        "Every image below is a file from **Wikimedia Commons**, downloaded by",
        "`backend/seed_media_fetch.py` (`make fetchmedia`) and used as demo",
        "imagery for the funeral-home vertical. Licences are as recorded on each",
        "file's Commons description page; follow the link for the authoritative",
        "terms and the full author credit.",
        "",
        "| File | Source (Commons) | Author | Licence |",
        "| --- | --- | --- | --- |",
    ]
    for slug in sorted(SOURCES):
        if not _dest(root, slug).exists():
            continue
        c = CREDITS.get(slug, {})
        title = c.get("title", slug).replace("|", "/")
        author = (c.get("author") or "see file page").replace("|", "/")
        page = c.get("page", "")
        link = f"[{title}]({page})" if page else title
        lines.append(f"| `{slug}.jpg` | {link} | {author} | {c.get('license', 'see file page')} |")
    lines.append("")
    dest = root / "CREDITS.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = ensure_media()
    print(
        f"media root : {s['root']}\n"
        f"downloaded : {s['downloaded']}\n"
        f"cached     : {s['skipped']}\n"
        f"failed     : {s['failed']}\n"
        f"total size : {s['bytes'] / 1024 / 1024:.1f} MiB"
    )
    for miss in s["misses"]:
        print("  MISS", miss)
    return 0  # a miss is not an error: the seed falls back to gradients


if __name__ == "__main__":
    raise SystemExit(main())
