import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.enums import CategoryType
from app.db.models.category import Category

DEFAULT_CATEGORIES: list[tuple[str, CategoryType]] = [
    ("Salary", CategoryType.INCOME),
    ("Freelance", CategoryType.INCOME),
    ("Business income", CategoryType.INCOME),
    ("Interest", CategoryType.INCOME),
    ("Other income", CategoryType.INCOME),
    ("Food", CategoryType.EXPENSE),
    ("Transportation", CategoryType.EXPENSE),
    ("Housing", CategoryType.EXPENSE),
    ("Utilities", CategoryType.EXPENSE),
    ("Healthcare", CategoryType.EXPENSE),
    ("Education", CategoryType.EXPENSE),
    ("Shopping", CategoryType.EXPENSE),
    ("Entertainment", CategoryType.EXPENSE),
    ("Debt payment", CategoryType.EXPENSE),
    ("Insurance", CategoryType.EXPENSE),
    ("Other expense", CategoryType.EXPENSE),
]


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_defaults(self) -> None:
        existing = self.db.scalar(select(Category.id).where(Category.is_system.is_(True)).limit(1))
        if existing:
            return
        for name, category_type in DEFAULT_CATEGORIES:
            self.db.add(
                Category(
                    user_id=None,
                    name=name,
                    category_type=category_type,
                    is_system=True,
                    is_active=True,
                )
            )
        self.db.commit()

    def get_by_id(self, category_id: uuid.UUID, user_id: uuid.UUID) -> Category | None:
        stmt = select(Category).where(
            Category.id == category_id,
            or_(Category.user_id == user_id, Category.is_system.is_(True)),
        )
        return self.db.scalar(stmt)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        category_type: CategoryType | None = None,
        include_inactive: bool = False,
    ) -> list[Category]:
        stmt = select(Category).where(
            or_(Category.user_id == user_id, Category.is_system.is_(True)),
        )
        if category_type:
            stmt = stmt.where(Category.category_type == category_type)
        if not include_inactive:
            stmt = stmt.where(Category.is_active.is_(True))
        stmt = stmt.order_by(Category.is_system.desc(), Category.name.asc())
        return list(self.db.scalars(stmt))

    def create(self, category: Category) -> Category:
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def update(self, category: Category) -> Category:
        self.db.commit()
        self.db.refresh(category)
        return category
