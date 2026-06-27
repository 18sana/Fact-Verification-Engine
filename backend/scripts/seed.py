"""Seed database with sample sources, evidence, and benchmark data."""

import asyncio
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import EvidenceDB, Source
from app.db.session import async_session_factory
from app.retrieval.hybrid import EmbeddingService

SAMPLE_SOURCES = [
    {
        "title": "ICC Cricket World Cup 2011 Final",
        "url": "https://en.wikipedia.org/wiki/2011_Cricket_World_Cup_Final",
        "credibility": 0.9,
        "evidence": [
            "India won the 2011 Cricket World Cup by defeating Sri Lanka in the final at Wankhede Stadium, Mumbai on April 2, 2011.",
            "MS Dhoni captained the Indian cricket team during the 2011 World Cup campaign.",
            "India scored 277/4 in the final, chasing Sri Lanka's 274/6.",
        ],
    },
    {
        "title": "ESPNcricinfo - 2011 World Cup",
        "url": "https://www.espncricinfo.com/series/icc-cricket-world-cup-2010-11",
        "credibility": 0.95,
        "evidence": [
            "India beat Sri Lanka by 6 wickets in the 2011 Cricket World Cup final.",
            "MS Dhoni was named captain of the Indian team for the 2011 World Cup.",
            "The tournament was co-hosted by India, Sri Lanka, and Bangladesh.",
        ],
    },
    {
        "title": "BBC Sport - Cricket World Cup 2011",
        "url": "https://www.bbc.com/sport/cricket/2011-world-cup",
        "credibility": 0.88,
        "evidence": [
            "India claimed their second World Cup title in 2011, 28 years after their first in 1983.",
            "Dhoni finished the final with an unbeaten 91, hitting the winning six.",
        ],
    },
    {
        "title": "NASA Climate Data",
        "url": "https://climate.nasa.gov/",
        "credibility": 0.95,
        "evidence": [
            "The global average temperature has risen by approximately 1.1 degrees Celsius since the late 19th century.",
            "Arctic sea ice extent has declined significantly over the past four decades.",
        ],
    },
    {
        "title": "WHO COVID-19 Report",
        "url": "https://www.who.int/emergencies/diseases/novel-coronavirus-2019",
        "credibility": 0.92,
        "evidence": [
            "COVID-19 was declared a global pandemic by WHO on March 11, 2020.",
            "Vaccination programs began globally in late 2020 and early 2021.",
        ],
    },
    {
        "title": "NASA Solar System Exploration",
        "url": "https://science.nasa.gov/solar-system/",
        "credibility": 0.98,
        "evidence": [
            "Earth orbits the Sun at an average distance of about 149.6 million kilometers (1 astronomical unit).",
            "Earth completes one orbit around the Sun in approximately 365.25 days, defining one tropical year.",
            "A common calendar year has 365 days; leap years add an extra day to account for the fractional orbital period.",
        ],
    },
    {
        "title": "Britannica - Earth",
        "url": "https://www.britannica.com/place/Earth",
        "credibility": 0.95,
        "evidence": [
            "Earth revolves around the Sun once every 365.256 solar days.",
            "The Earth's orbital period is the basis for the length of the year in most calendar systems.",
        ],
    },
    {
        "title": "NASA - Apollo 11 Mission",
        "url": "https://www.nasa.gov/mission_pages/apollo/apollo-11.html",
        "credibility": 0.98,
        "evidence": [
            "Apollo 11 landed on the Moon on July 20, 1969, and Neil Armstrong became the first human to walk on the lunar surface.",
            "Buzz Aldrin joined Armstrong on the Moon while Michael Collins orbited in the command module.",
            "The Apollo 11 mission fulfilled President Kennedy's goal of landing Americans on the Moon before the end of the 1960s.",
        ],
    },
    {
        "title": "CERN - World Wide Web",
        "url": "https://home.cern/science/computing/birth-web",
        "credibility": 0.96,
        "evidence": [
            "Tim Berners-Lee invented the World Wide Web in 1989 while working at CERN in Switzerland.",
            "The first website was hosted at CERN and went online in 1991.",
            "Berners-Lee proposed HTTP, HTML, and URLs as open standards for sharing information globally.",
        ],
    },
    {
        "title": "Britannica - Mount Everest",
        "url": "https://www.britannica.com/place/Mount-Everest",
        "credibility": 0.94,
        "evidence": [
            "Mount Everest is the highest mountain on Earth above sea level, with a summit elevation of 8,849 meters (29,032 feet).",
            "Sir Edmund Hillary of New Zealand and Tenzing Norgay of Nepal were the first climbers confirmed to reach the summit on May 29, 1953.",
            "Everest lies on the border between Nepal and the Tibet Autonomous Region of China.",
        ],
    },
    {
        "title": "National Geographic - Amazon River",
        "url": "https://www.nationalgeographic.com/environment/article/amazon-river",
        "credibility": 0.91,
        "evidence": [
            "The Amazon River in South America is widely considered the largest river by discharge volume in the world.",
            "The Amazon basin spans roughly 40 percent of the South American continent.",
            "Scientists debate whether the Amazon or the Nile is the longest river, depending on measurement methods.",
        ],
    },
    {
        "title": "Nobel Prize - Penicillin Discovery",
        "url": "https://www.nobelprize.org/prizes/medicine/1945/fleming/facts/",
        "credibility": 0.97,
        "evidence": [
            "Alexander Fleming discovered penicillin in 1928 after noticing mold inhibiting bacterial growth in a petri dish.",
            "Fleming shared the 1945 Nobel Prize in Physiology or Medicine with Howard Florey and Ernst Chain for developing penicillin as a life-saving antibiotic.",
            "Penicillin became the first widely used antibiotic and transformed modern medicine.",
        ],
    },
    {
        "title": "FIFA - 2022 World Cup",
        "url": "https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/qatar2022",
        "credibility": 0.93,
        "evidence": [
            "Argentina won the 2022 FIFA World Cup in Qatar, defeating France in the final on penalties after a 3-3 draw.",
            "Lionel Messi captained Argentina and won the Golden Ball as the tournament's best player.",
            "The 2022 World Cup was the first men's FIFA World Cup held in the Middle East.",
        ],
    },
    {
        "title": "Smithsonian - Photosynthesis",
        "url": "https://ocean.si.edu/ocean-life/plants-algae/photosynthesis",
        "credibility": 0.92,
        "evidence": [
            "Photosynthesis is the process by which plants and algae convert light energy into chemical energy stored in glucose.",
            "During photosynthesis, organisms absorb carbon dioxide and release oxygen as a byproduct.",
            "Chlorophyll in plant cells captures sunlight to drive the photosynthetic reaction.",
        ],
    },
    {
        "title": "Encyclopedia Britannica - Marie Curie",
        "url": "https://www.britannica.com/biography/Marie-Curie",
        "credibility": 0.96,
        "evidence": [
            "Marie Curie was the first woman to win a Nobel Prize and the only person to win Nobel Prizes in two different sciences.",
            "She won the Nobel Prize in Physics in 1903 and the Nobel Prize in Chemistry in 1911 for her work on radioactivity.",
            "Curie discovered the elements polonium and radium with her husband Pierre Curie.",
        ],
    },
    {
        "title": "Apple Newsroom - iPhone Introduction",
        "url": "https://www.apple.com/newsroom/2007/01/09Apple-Reinvents-the-Phone-with-iPhone/",
        "credibility": 0.94,
        "evidence": [
            "Apple introduced the first iPhone on January 9, 2007, at the Macworld conference in San Francisco.",
            "Steve Jobs unveiled the iPhone as combining a mobile phone, widescreen iPod, and internet communicator.",
            "The original iPhone went on sale in the United States on June 29, 2007.",
        ],
    },
]


async def seed():
    settings = get_settings()
    embedding_service = EmbeddingService(settings)

    async with async_session_factory() as session:
        added = 0
        for src_data in SAMPLE_SOURCES:
            existing = await session.execute(
                select(Source).where(Source.title == src_data["title"])
            )
            if existing.scalar_one_or_none():
                continue

            source = Source(
                id=uuid.uuid4(),
                title=src_data["title"],
                url=src_data["url"],
                credibility=src_data["credibility"],
            )
            session.add(source)
            await session.flush()

            for content in src_data["evidence"]:
                embedding = (await embedding_service.embed([content]))[0].tolist()
                evidence = EvidenceDB(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    content=content,
                    embedding=embedding,
                )
                session.add(evidence)
            added += 1

        if added:
            await session.commit()
            print(f"Seeded {added} new source(s) with evidence.")
        else:
            print("All sample sources already present, nothing to seed.")


if __name__ == "__main__":
    asyncio.run(seed())
