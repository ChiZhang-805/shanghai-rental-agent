import hashlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.db import SessionLocal, init_db
from app.models.listing import Listing, ListingEmbedding
from app.services.embedding_service import EmbeddingService
from app.services.listing_service import ListingService


def main() -> None:
    init_db()
    embedding_service = EmbeddingService()
    with SessionLocal() as session:
        listings = list(session.scalars(select(Listing).where(Listing.city == "上海")).all())
        session.execute(delete(ListingEmbedding))
        texts = [ListingService.make_listing_text(listing) for listing in listings]
        embeddings = embedding_service.embed_texts(texts)
        for listing, text_value, embedding in zip(listings, texts, embeddings, strict=False):
            session.add(
                ListingEmbedding(
                    listing_id=listing.id,
                    embedding=embedding,
                    text_hash=hashlib.sha256(text_value.encode("utf-8")).hexdigest(),
                )
            )
        session.commit()
    print(f"Embedded {len(listings)} listings.")


if __name__ == "__main__":
    main()
