import csv
import hashlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete

from app.db import SessionLocal, init_db
from app.models.listing import Listing, ListingEmbedding
from app.models.policy import PolicyChunk, PolicyDocument
from app.services.embedding_service import EmbeddingService
from app.services.listing_service import ListingService
from app.services.policy_service import PolicyService


def _int_or_none(value: str) -> int | None:
    return int(value) if value else None


def _float_or_none(value: str) -> float | None:
    return float(value) if value else None


def _bool_or_none(value: str) -> bool | None:
    if value == "":
        return None
    return value.lower() in {"true", "1", "yes", "y"}


def main() -> None:
    init_db()
    embedding_service = EmbeddingService()
    with SessionLocal() as session:
        session.execute(delete(ListingEmbedding))
        session.execute(delete(Listing))
        session.execute(delete(PolicyChunk))
        session.execute(delete(PolicyDocument))

        csv_path = Path("data/demo/listings.csv")
        with csv_path.open(encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            listings: list[Listing] = []
            for row in reader:
                listing = Listing(
                    listing_code=row["listing_code"],
                    city=row["city"],
                    district=row["district"],
                    subdistrict=row.get("subdistrict") or None,
                    community_name=row["community_name"],
                    address_masked=row.get("address_masked") or None,
                    lat=_float_or_none(row.get("lat", "")),
                    lon=_float_or_none(row.get("lon", "")),
                    purpose=row["purpose"],
                    property_type=row.get("property_type") or "residential",
                    title=row["title"],
                    description=row.get("description") or None,
                    rooms=_int_or_none(row.get("rooms", "")),
                    halls=_int_or_none(row.get("halls", "")),
                    bathrooms=_int_or_none(row.get("bathrooms", "")),
                    area_sqm=float(row["area_sqm"]),
                    floor=row.get("floor") or None,
                    total_floors=_int_or_none(row.get("total_floors", "")),
                    orientation=row.get("orientation") or None,
                    decoration=row.get("decoration") or None,
                    built_year=_int_or_none(row.get("built_year", "")),
                    has_elevator=_bool_or_none(row.get("has_elevator", "")),
                    sale_price_total=_int_or_none(row.get("sale_price_total", "")),
                    rent_price_monthly=_int_or_none(row.get("rent_price_monthly", "")),
                    verification_code=row.get("verification_code") or None,
                    verification_status=row["verification_status"],
                    entrusted_status=row["entrusted_status"],
                    listing_status=row["listing_status"],
                    source=row.get("source") or "internal",
                )
                session.add(listing)
                listings.append(listing)
            session.flush()

            texts = [ListingService.make_listing_text(listing) for listing in listings]
            embeddings = embedding_service.embed_texts(texts)
            for listing, text_value, embedding in zip(listings, texts, embeddings, strict=False):
                text_hash = hashlib.sha256(text_value.encode("utf-8")).hexdigest()
                session.add(
                    ListingEmbedding(
                        listing_id=listing.id,
                        embedding=embedding,
                        text_hash=text_hash,
                    )
                )
        session.commit()
        policy_result = PolicyService(embedding_service=embedding_service).ingest_directory(
            session, Path("data/policies")
        )
    print(
        "Seeded demo listings and policies: "
        f"{policy_result.documents} policy docs, {policy_result.chunks} chunks."
    )


if __name__ == "__main__":
    main()
